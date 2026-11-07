from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from analytics.views import get_accessible_venues
from cameras.models import Camera
from monitoring.models import AuditLog
from monitoring.services.audit import log_action
from operations.models import RestaurantTable

from .forms import LoginForm
from .forms_management import CameraForm, StaffCreateForm, StaffEditForm, TableForm, assignable_roles, is_manager
from .permissions import get_or_create_profile

DENIED = "El centro de gestión es solo para dueños, administradores y supervisores."


def _actor(request):
    if not is_manager(request.user):
        raise PermissionDenied(DENIED)
    profile = get_or_create_profile(request.user)
    return profile, get_accessible_venues(profile)


def _managed_users(actor, venues):
    users = User.objects.filter(profile__isnull=False).select_related("profile").prefetch_related("profile__venues")
    if not (actor.is_platform_admin or actor.user.is_superuser):
        users = users.filter(profile__venues__in=venues, is_superuser=False).distinct()
        allowed = set(assignable_roles(actor))
        return [u for u in users.order_by("first_name", "username") if u.profile.role in allowed or u == actor.user]
    return list(users.order_by("first_name", "username"))


def _errors(form):
    return " ".join(f"{form.fields[name].label if name in form.fields else ''}: {' '.join(errs)}".strip(": ")
                    for name, errs in form.errors.items())


def management_login(request):
    if request.user.is_authenticated and is_manager(request.user):
        return redirect("management:home")
    form = LoginForm(request, data=request.POST or None)
    error = None
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if not is_manager(user):
            error = "Este acceso es solo para dueños, administradores y supervisores. Usa el acceso del personal."
        else:
            login(request, user)
            log_action(request, action=AuditLog.Action.LOGIN, module="authentication",
                       description=f"Inicio de sesión por el acceso de gestión ({user.get_username()}).")
            return redirect("management:home")
    return render(request, "authentication/management_login.html", {"form": form, "error": error})


@login_required
def home(request):
    actor, venues = _actor(request)
    users = _managed_users(actor, venues)
    tables = RestaurantTable.objects.filter(venue__in=venues).select_related("venue").order_by("venue__name", "zone_name", "code")
    cameras = Camera.objects.filter(venue__in=venues).select_related("venue", "table").order_by("venue__name", "name")
    zones = sorted({t.zone_name for t in tables if t.zone_name})
    return render(request, "authentication/management/home.html", {
        "users": users, "tables": tables, "cameras": cameras, "zones": zones,
        "service_roles": ["waiter", "cashier", "kitchen", "bar", "operator"],
        "security_warnings": __import__("core.security_checks", fromlist=["x"]).security_warnings(),
        "staff_form": StaffCreateForm(actor=actor, venues=venues), "table_form": TableForm(venues=venues),
        "camera_form": CameraForm(venues=venues),
        "kpis": {"staff": sum(1 for u in users if u.is_active), "tables": tables.count(), "zones": len(zones),
                 "cameras": cameras.count(), "entrances": cameras.filter(is_entrance=True).count()},
    })


@login_required
@require_POST
def staff_create(request):
    actor, venues = _actor(request)
    form = StaffCreateForm(request.POST, actor=actor, venues=venues)
    if form.is_valid():
        user = form.save()
        log_action(request, action=AuditLog.Action.CREATE, module="authentication", object_type="User",
                   object_id=str(user.pk), description=f"Creó a {user.get_username()} con rol {user.profile.get_role_display()}.")
        messages.success(request, f"{user.first_name or user.username} fue agregado como {user.profile.get_role_display().lower()}.")
    else:
        messages.error(request, "No se pudo crear la cuenta. " + _errors(form))
    return redirect("management:home")


@login_required
def staff_edit(request, user_id):
    actor, venues = _actor(request)
    target = get_object_or_404(User.objects.select_related("profile"), pk=user_id)
    if target not in _managed_users(actor, venues):
        raise PermissionDenied("No puedes administrar a este usuario.")
    initial = {"role": target.profile.role, "venues": target.profile.venues.all(), "zones": target.profile.zones,
               "is_active": target.is_active}
    form = StaffEditForm(request.POST or None, actor=actor, venues=venues, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save(target)
        log_action(request, action=AuditLog.Action.UPDATE, module="authentication", object_type="User",
                   object_id=str(target.pk), description=f"Actualizó la cuenta de {target.get_username()}.")
        messages.success(request, "Cambios guardados.")
        return redirect("management:home")
    return render(request, "authentication/management/staff_edit.html", {"form": form, "target": target})


@login_required
@require_POST
def table_create(request):
    _, venues = _actor(request)
    form = TableForm(request.POST, venues=venues)
    if form.is_valid():
        table = form.save()
        messages.success(request, f"Mesa {table.code} creada en {table.zone_name or 'la zona principal'}.")
    else:
        messages.error(request, "No se pudo crear la mesa. " + _errors(form))
    return redirect("management:home")


@login_required
@require_POST
def camera_create(request):
    _, venues = _actor(request)
    form = CameraForm(request.POST, venues=venues)
    if form.is_valid():
        camera = form.save()
        messages.success(request, f"Cámara «{camera.name}» registrada.")
    else:
        messages.error(request, "No se pudo registrar la cámara. " + _errors(form))
    return redirect("management:home")


@login_required
def staff_qr(request, user_id):
    from operations.services.pairing import can_pair, pair_context

    actor, venues = _actor(request)
    target = get_object_or_404(User.objects.select_related("profile"), pk=user_id)
    if target not in _managed_users(actor, venues) or not can_pair(target):
        raise PermissionDenied("Solo puedes generar códigos de acceso para el personal de servicio de tus locales.")
    log_action(request, action=AuditLog.Action.CREATE, module="authentication", object_type="Pairing",
               object_id=str(target.pk), description=f"Generó un código QR de acceso para {target.get_username()}.")
    return render(request, "operations/pair.html", pair_context(request, target))


@login_required
def camera_discover(request):
    """Detecta cámaras locales o prueba una de red, y las registra con su uso (mesa, entrada o caja)."""
    from ai_vision.models import AnalysisSession
    from ai_vision.services.discovery import probe_local, probe_url, validate_url

    actor, venues = _actor(request)
    registered = {c.source: c for c in Camera.objects.filter(venue__in=venues)}
    running = set(AnalysisSession.objects.filter(status=AnalysisSession.Status.RUNNING, camera__venue__in=venues)
                  .values_list("camera__source", flat=True))

    if request.method == "POST" and request.POST.get("accion") == "registrar":
        source = (request.POST.get("source") or "").strip()
        purpose = request.POST.get("uso", "mesa")
        venue = venues.filter(pk=request.POST.get("venue")).first()
        table = RestaurantTable.objects.filter(pk=request.POST.get("table") or 0, venue__in=venues).first()
        try:
            if not source.isdigit():
                source = validate_url(source)
        except ValueError as error:
            messages.error(request, str(error))
            return redirect("management:camera_discover")
        if venue is None:
            messages.error(request, "Elige el local de la cámara.")
            return redirect("management:camera_discover")
        if purpose == "mesa" and table is None:
            messages.error(request, "Elige la mesa que cubre la cámara.")
            return redirect("management:camera_discover")
        url_type = next((value for value, _ in Camera.SourceType.choices
                         if value not in (Camera.SourceType.WEBCAM, Camera.SourceType.DEMO)), Camera.SourceType.WEBCAM)
        camera = Camera.objects.create(
            venue=venue, name=(request.POST.get("name") or "").strip()[:100] or f"Cámara {source}",
            source=source, source_type=Camera.SourceType.WEBCAM if source.isdigit() else url_type,
            table=table if purpose == "mesa" else None, zone_name=(request.POST.get("zone") or "").strip()[:80],
            is_entrance=purpose == "entrada", is_checkout=purpose == "caja", is_active=True,
        )
        log_action(request, action=AuditLog.Action.CREATE, module="cameras", venue=venue, object_type="Camera",
                   object_id=str(camera.pk), description=f"Registró la cámara «{camera.name}» ({purpose}) desde la detección.")
        messages.success(request, f"Cámara «{camera.name}» registrada como cámara de {purpose}.")
        return redirect("management:camera_discover")

    tested = None
    if request.method == "POST" and request.POST.get("accion") == "probar":
        try:
            tested = probe_url(request.POST.get("url", ""))
            tested["registered"] = registered.get(tested["source"])
        except ValueError as error:
            messages.error(request, str(error))

    devices = []
    if request.GET.get("buscar") == "1":
        for device in probe_local():
            device["registered"] = registered.get(device["source"])
            devices.append(device)
    busy = [c for c in registered.values() if c.source in running]
    return render(request, "authentication/management/camera_discover.html", {
        "devices": devices, "searched": request.GET.get("buscar") == "1", "tested": tested, "busy": busy,
        "venues": venues, "tables": RestaurantTable.objects.filter(venue__in=venues).order_by("code"),
    })
