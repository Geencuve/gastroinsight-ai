from datetime import timedelta

import segno
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from analytics.views import get_accessible_venues
from authentication.models import Profile
from authentication.permissions import get_or_create_profile
from menus.models import Dish
from sales.models import Order, OrderItem

from .models import RestaurantTable, SatisfactionEvaluation, ServiceSession, WaitlistEntry
from .services.floor import PENDING, build_floor, minutes_between, thermometer

FEEDBACK_SALT = "gi-session-feedback"
FEEDBACK_MAX_AGE = 3 * 3600
SCORES = [(i, f"{i} ★") for i in range(1, 6)]


def _venues(request):
    return get_accessible_venues(get_or_create_profile(request.user))


def _require_operator(request):
    if get_or_create_profile(request.user).role in (Profile.Role.VIEWER, Profile.Role.KITCHEN, Profile.Role.BAR):
        raise PermissionDenied("Tu rol no puede modificar la sala.")


# ---------------- Mapa de sala ----------------
@login_required
def floor_map(request):
    return render(request, "operations/floor.html", build_floor(_venues(request)))


@login_required
def floor_board(request):
    return render(request, "operations/_floor_board.html", build_floor(_venues(request)))


@login_required
@require_POST
def waitlist_add(request):
    _require_operator(request)
    venues = _venues(request)
    venue = venues.filter(pk=request.POST.get("venue")).first() or venues.first()
    if venue is None:
        messages.error(request, "No tienes locales asignados.")
        return redirect("floor:map")
    try:
        guests = max(1, min(30, int(request.POST.get("guests", 2))))
    except ValueError:
        guests = 2
    WaitlistEntry.objects.create(venue=venue, guests=guests, created_by=request.user,
                                 party_name=(request.POST.get("party_name") or "").strip()[:80])
    messages.success(request, f"Llegada registrada: {guests} persona(s) esperando mesa.")
    return redirect("floor:map")


@login_required
@require_POST
def waitlist_seat(request, entry_id):
    _require_operator(request)
    entry = get_object_or_404(WaitlistEntry, pk=entry_id, venue__in=_venues(request),
                              seated_at__isnull=True, cancelled=False)
    table = RestaurantTable.objects.filter(pk=request.POST.get("table"), venue=entry.venue, is_active=True).first()
    if table is None or ServiceSession.objects.filter(table=table, status=ServiceSession.Status.OPEN).exists():
        messages.error(request, "Elige una mesa libre del mismo local.")
        return redirect("floor:map")
    session = ServiceSession.objects.create(table=table, guests_count=entry.guests, arrived_at=entry.arrived_at,
                                            created_by=request.user)
    entry.seated_at, entry.service_session = timezone.now(), session
    entry.save(update_fields=["seated_at", "service_session"])
    messages.success(request, f"Mesa {table.code} asignada tras {entry.waiting_minutes} min de espera.")
    return redirect("floor:map")


@login_required
@require_POST
def waitlist_cancel(request, entry_id):
    _require_operator(request)
    entry = get_object_or_404(WaitlistEntry, pk=entry_id, venue__in=_venues(request), seated_at__isnull=True)
    entry.cancelled = True
    entry.save(update_fields=["cancelled"])
    messages.info(request, "El grupo se registró como retirado sin mesa.")
    return redirect("floor:map")


@login_required
@require_POST
def toggle_bill(request, session_id):
    _require_operator(request)
    session = get_object_or_404(ServiceSession, pk=session_id, table__venue__in=_venues(request),
                                status=ServiceSession.Status.OPEN)
    session.bill_requested_at = None if session.bill_requested_at else timezone.now()
    session.save(update_fields=["bill_requested_at"])
    return redirect(request.POST.get("next") or "floor:map")


# ---------------- QR por atención (3 horas) ----------------
def session_token(session):
    return signing.TimestampSigner(salt=FEEDBACK_SALT).sign(str(session.pk))


@login_required
def session_qr(request, session_id):
    session = get_object_or_404(ServiceSession.objects.select_related("table__venue"), pk=session_id,
                                table__venue__in=_venues(request))
    url = request.build_absolute_uri(reverse("feedback:session_form", args=[session_token(session)]))
    svg = segno.make(url, error="m").svg_inline(scale=8, dark="#111111", light="#ffffff")
    return render(request, "operations/session_qr.html", {
        "session": session, "table": session.table, "url": url, "qr_svg": mark_safe(svg),
        "expires_at": timezone.now() + timedelta(seconds=FEEDBACK_MAX_AGE),
    })


class SessionFeedbackForm(forms.Form):
    rating = forms.TypedChoiceField(label="¿Cómo fue tu experiencia en general?", choices=SCORES, coerce=int,
                                    widget=forms.RadioSelect)
    value_rating = forms.TypedChoiceField(label="Relación precio-calidad", choices=SCORES, coerce=int,
                                          required=False, empty_value=None, widget=forms.RadioSelect)
    return_intent = forms.ChoiceField(label="¿Volverías?", choices=[("yes", "Sí"), ("maybe", "Tal vez"), ("no", "No")],
                                      required=False, widget=forms.RadioSelect)
    cleanliness_rating = forms.TypedChoiceField(label="Limpieza del local", choices=SCORES, coerce=int,
                                                required=False, empty_value=None, widget=forms.RadioSelect)
    restroom_rating = forms.TypedChoiceField(label="Baños (si los usaste)", choices=SCORES, coerce=int,
                                             required=False, empty_value=None, widget=forms.RadioSelect)
    ambience_rating = forms.TypedChoiceField(label="Ambiente y comodidad (mesas, sillas, temperatura, ruido)",
                                             choices=SCORES, coerce=int, required=False, empty_value=None,
                                             widget=forms.RadioSelect)
    dish = forms.ModelChoiceField(queryset=Dish.objects.none(), required=False,
                                  label="¿Qué plato quieres evaluar? (opcional)")
    comment = forms.CharField(label="Comentario (opcional)", required=False, max_length=500,
                              widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, session=None, **kwargs):
        super().__init__(*args, **kwargs)
        ids = OrderItem.objects.filter(order__service_session=session).values_list("dish_id", flat=True)
        dishes = Dish.objects.filter(id__in=ids)
        if not dishes.exists() and session is not None:
            dishes = Dish.objects.filter(menu__venue=session.table.venue, is_available=True)
        self.fields["dish"].queryset = dishes.order_by("name")


def session_feedback(request, token):
    try:
        value = signing.TimestampSigner(salt=FEEDBACK_SALT).unsign(token, max_age=FEEDBACK_MAX_AGE)
        session = ServiceSession.objects.select_related("table__venue").get(pk=int(value))
    except signing.SignatureExpired:
        return render(request, "operations/session_feedback.html", {"expired": True}, status=410)
    except (signing.BadSignature, ServiceSession.DoesNotExist, ValueError):
        raise Http404("Código de opinión no válido.")

    venue = session.table.venue
    context = {"session": session, "table": session.table, "venue": venue,
               "menu_url": reverse("menus:public", args=[venue.id])}
    if SatisfactionEvaluation.objects.filter(service_session=session,
                                             source=SatisfactionEvaluation.Source.CUSTOMER_QR).exists():
        return render(request, "operations/session_feedback.html", {**context, "done": True})

    form = SessionFeedbackForm(request.POST or None, session=session)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        evaluation = SatisfactionEvaluation(
            service_session=session, dish=data["dish"], rating=data["rating"], comment=data["comment"].strip(),
            source=SatisfactionEvaluation.Source.CUSTOMER_QR, value_rating=data["value_rating"],
            return_intent=data["return_intent"] or "", cleanliness_rating=data["cleanliness_rating"],
            restroom_rating=data["restroom_rating"], ambience_rating=data["ambience_rating"],
        )
        try:
            evaluation.full_clean()
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        else:
            evaluation.save()
            return redirect(request.path)
    return render(request, "operations/session_feedback.html", {**context, "form": form})


# ---------------- Caja ----------------
@login_required
def cashier(request):
    now = timezone.now()
    items = []
    for session in (ServiceSession.objects.filter(table__venue__in=_venues(request), status=ServiceSession.Status.OPEN)
                    .select_related("table")):
        pending = list(Order.objects.filter(service_session=session, status__in=PENDING).order_by("id"))
        if not pending and not session.bill_requested_at:
            continue
        items.append({"session": session, "orders": pending, "minutes": minutes_between(session.started_at, now),
                      "thermo": thermometer(session, now)})
    items.sort(key=lambda item: (item["session"].bill_requested_at is None, -(item["minutes"] or 0)))
    return render(request, "operations/cashier.html", {"items": items})
