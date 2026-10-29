from collections import Counter

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from analytics.views import get_accessible_venues
from authentication.permissions import get_or_create_profile
from monitoring.models import AuditLog
from monitoring.services.audit import log_action

from .models import TRAINING_ATTENTION_LABELS, TRAINING_EXPRESSION_LABELS, CalibrationModel, TrainingSample
from .services import training
from .services.vision_pipeline import ModelsNotAvailable

MAX_FILES = 50
MAX_MB = 5


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": "image/jpeg,image/png"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(item, initial) for item in data]
        return [single(data, initial)]


class TrainingUploadForm(forms.Form):
    kind = forms.ChoiceField(choices=TrainingSample.Kind.choices, label="Tipo de dato")
    label = forms.ChoiceField(choices=TRAINING_EXPRESSION_LABELS + TRAINING_ATTENTION_LABELS,
                              label="Etiqueta real de las imágenes")
    images = MultipleImageField(label="Imágenes (JPG o PNG)")
    consent = forms.BooleanField(
        required=True,
        label="Confirmo que cuento con el consentimiento informado de las personas que aparecen y que las "
              "imágenes se usarán solo para evaluar y calibrar el modelo.",
    )

    def clean(self):
        data = super().clean()
        kind, label, images = data.get("kind"), data.get("label"), data.get("images") or []
        valid = dict(TRAINING_EXPRESSION_LABELS if kind == TrainingSample.Kind.EXPRESSION else TRAINING_ATTENTION_LABELS)
        if label and label not in valid:
            self.add_error("label", "La etiqueta no corresponde al tipo de dato elegido.")
        if len(images) > MAX_FILES:
            self.add_error("images", f"Puedes subir hasta {MAX_FILES} imágenes por vez.")
        if any(getattr(image, "size", 0) > MAX_MB * 1024 * 1024 for image in images):
            self.add_error("images", f"Cada imagen debe pesar menos de {MAX_MB} MB.")
        return data


def _manager(request):
    profile = get_or_create_profile(request.user)
    if not (profile.is_platform_admin or profile.is_venue_admin):
        raise PermissionDenied("Solo los administradores pueden gestionar los datos de entrenamiento.")
    return profile


def _bars(kind, labels):
    counts = Counter(TrainingSample.objects.filter(kind=kind).values_list("label", flat=True))
    top = max(counts.values(), default=0) or 1
    return [{"label": name, "value": counts.get(value, 0), "pct": max(2, round(100 * counts.get(value, 0) / top))}
            for value, name in labels]


@login_required
def training_home(request):
    profile = _manager(request)
    venue = get_accessible_venues(profile).first()
    form = TrainingUploadForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        saved, errors = 0, []
        try:
            for image in form.cleaned_data["images"]:
                sample, error = training.process_upload(
                    image, form.cleaned_data["kind"], form.cleaned_data["label"], request.user, venue,
                )
                if sample:
                    saved += 1
                else:
                    errors.append(error)
        except ModelsNotAvailable as error:
            messages.error(request, str(error))
            return redirect("ai_vision:training")
        if saved:
            log_action(request, action=AuditLog.Action.CREATE, module="ai_vision", venue=venue,
                       object_type="TrainingSample", object_id=str(saved),
                       description=f"Cargó {saved} muestra(s) de entrenamiento con consentimiento confirmado.")
            messages.success(request, f"{saved} imagen(es) procesada(s). Solo se guardó el recorte del rostro.")
        for error in errors[:5]:
            messages.warning(request, error)
        if len(errors) > 5:
            messages.warning(request, f"…y {len(errors) - 5} imagen(es) más sin rostro detectable.")
        return redirect("ai_vision:training")

    active = CalibrationModel.objects.filter(kind=TrainingSample.Kind.EXPRESSION, active=True).first()
    base = training.evaluate_expression()
    calibrated = training.evaluate_expression(active.weights) if active and base else None
    return render(request, "ai_vision/training.html", {
        "form": form,
        "label_groups": [
            {"kind": "expression", "title": "Expresiones", "options": TRAINING_EXPRESSION_LABELS},
            {"kind": "attention", "title": "Atención", "options": TRAINING_ATTENTION_LABELS},
        ],
        "expression_bars": _bars(TrainingSample.Kind.EXPRESSION, TRAINING_EXPRESSION_LABELS),
        "attention_bars": _bars(TrainingSample.Kind.ATTENTION, TRAINING_ATTENTION_LABELS),
        "eval_base": base,
        "eval_calibrated": calibrated,
        "eval_shown": calibrated or base,
        "can_train": training.can_train_expression(),
        "calibrations": CalibrationModel.objects.filter(kind=TrainingSample.Kind.EXPRESSION)[:6],
        "attention": training.evaluate_attention(),
        "samples": TrainingSample.objects.all()[:48],
        "total_samples": TrainingSample.objects.count(),
        "min_per_label": training.MIN_PER_LABEL,
        "min_total": training.MIN_TOTAL,
    })


@login_required
@require_POST
def training_train(request):
    _manager(request)
    try:
        calibration = training.train_expression_calibration(request.user)
    except ValueError as error:
        messages.error(request, str(error))
    else:
        log_action(request, action=AuditLog.Action.CREATE, module="ai_vision", object_type="CalibrationModel",
                   object_id=str(calibration.pk),
                   description=f"Entrenó una calibración: {calibration.accuracy_before}% → {calibration.accuracy_after}%.")
        messages.success(request, f"Calibración entrenada: precisión {calibration.accuracy_before:.1f}% → "
                                  f"{calibration.accuracy_after:.1f}% (validación cruzada). Actívala para usarla.")
    return redirect("ai_vision:training")


@login_required
@require_POST
def training_toggle(request, calibration_id):
    _manager(request)
    calibration = get_object_or_404(CalibrationModel, pk=calibration_id)
    training.activate_calibration(calibration, not calibration.active)
    state = "activada" if calibration.active else "desactivada"
    log_action(request, action=AuditLog.Action.UPDATE, module="ai_vision", object_type="CalibrationModel",
               object_id=str(calibration.pk), description=f"Calibración #{calibration.pk} {state}.")
    messages.success(request, f"Calibración {state}. Se aplicará en los próximos análisis.")
    return redirect("ai_vision:training")


@login_required
@require_POST
def training_attention(request):
    _manager(request)
    evaluation = training.evaluate_attention()
    if not evaluation or not evaluation["can_suggest"]:
        messages.error(request, "Se necesitan al menos 6 imágenes de atención con ambas etiquetas.")
    else:
        training.apply_attention_threshold(evaluation["suggested"], request.user)
        log_action(request, action=AuditLog.Action.UPDATE, module="ai_vision", object_type="CalibrationModel",
                   object_id="attention", description=f"Umbral de atención ajustado a {evaluation['suggested']:.2f}.")
        messages.success(request, f"Umbral de búsqueda de atención ajustado a {evaluation['suggested']:.2f}.")
    return redirect("ai_vision:training")


@login_required
@require_POST
def training_delete(request, sample_id):
    _manager(request)
    get_object_or_404(TrainingSample, pk=sample_id).delete()
    log_action(request, action=AuditLog.Action.DELETE, module="ai_vision", object_type="TrainingSample",
               object_id=str(sample_id), description=f"Eliminó la muestra de entrenamiento #{sample_id}.")
    messages.success(request, "Muestra eliminada.")
    return redirect("ai_vision:training")


@login_required
@require_POST
def training_delete_all(request):
    _manager(request)
    total = 0
    for sample in TrainingSample.objects.all():
        sample.delete()
        total += 1
    log_action(request, action=AuditLog.Action.DELETE, module="ai_vision", object_type="TrainingSample",
               object_id="todas", description=f"Eliminó el conjunto de entrenamiento completo ({total} muestras).")
    messages.success(request, f"Se eliminaron {total} muestras y sus imágenes.")
    return redirect("ai_vision:training")
