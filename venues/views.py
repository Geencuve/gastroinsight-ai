from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from authentication.permissions import get_or_create_profile, user_can_access_venue, user_can_manage_venue
from monitoring.models import AuditLog
from monitoring.services.audit import log_action

from .forms import VenueForm
from .models import Venue


def _errors(form):
    return " ".join(e for errors in form.errors.values() for e in errors)


def venue_summary(venue):
    """Cifras y estado de la configuración de un local."""
    from cameras.models import Camera
    from menus.models import Dish, Menu
    from operations.models import ApiKey, RestaurantTable
    from operations.services.sustained import alert_settings
    from privacy.compliance import checklist
    from privacy.models import PrivacyPolicy

    tables = RestaurantTable.objects.filter(venue=venue)
    cameras = Camera.objects.filter(venue=venue)
    active_cameras = cameras.filter(is_active=True)
    unassigned = active_cameras.filter(table__isnull=True, is_entrance=False, is_checkout=False).count()
    policy = PrivacyPolicy.objects.filter(venue=venue).prefetch_related("authorizations").first()
    privacy = checklist(venue, policy)
    cfg = alert_settings(venue)
    menus = Menu.objects.filter(venue=venue, is_active=True)
    summary = {
        "tables": tables.count(),
        "zones": len({z for z in tables.values_list("zone_name", flat=True) if z}),
        "cameras": active_cameras.count(),
        "unassigned": unassigned,
        "staff": venue.assigned_profiles.filter(user__is_active=True).count(),
        "menus": menus.count(),
        "first_menu": menus.order_by("name").first(),
        "dishes": Dish.objects.filter(menu__in=menus, is_available=True).count(),
        "keys": ApiKey.objects.filter(venue=venue, is_active=True).count(),
        "impatience_pct": cfg.impatience_pct,
        "impatience_minutes": cfg.impatience_minutes,
        "privacy": privacy,
    }
    steps = [
        ("🪑 Crear las mesas", summary["tables"] > 0),
        ("👥 Agregar al personal", summary["staff"] > 0),
        ("📖 Cargar la carta con platos", summary["dishes"] > 0),
        ("📷 Registrar una cámara", summary["cameras"] > 0),
        ("🔒 Completar la política de privacidad", privacy["ok"]),
    ]
    summary["steps"] = [{"label": label, "ok": ok} for label, ok in steps]
    summary["steps_done"] = sum(1 for _, ok in steps if ok)
    summary["steps_pct"] = round(100 * summary["steps_done"] / len(steps))
    return summary


@login_required
def venue_list(request):
    profile = get_or_create_profile(request.user)
    venues = Venue.objects.all() if profile.is_platform_admin else Venue.objects.filter(is_active=True, assigned_profiles=profile)
    rows = [{"venue": v, "s": venue_summary(v), "can_manage": user_can_manage_venue(request.user, v)} for v in venues.order_by("name")]
    active = [r for r in rows if r["venue"].is_active]
    totals = {key: sum(r["s"][key] for r in active) for key in ("tables", "cameras", "staff")}
    totals["venues"] = len(active)
    return render(request, "venues/list.html", {
        "rows": active, "inactive": [r for r in rows if not r["venue"].is_active], "totals": totals,
        "can_create": profile.is_platform_admin, "form": VenueForm() if profile.is_platform_admin else None,
    })


@login_required
@require_POST
def venue_create(request):
    if not get_or_create_profile(request.user).is_platform_admin:
        raise PermissionDenied("Solo el administrador de la plataforma puede crear locales.")
    form = VenueForm(request.POST)
    if form.is_valid():
        venue = form.save()
        log_action(request, action=AuditLog.Action.CREATE, module="venues", venue=venue, object_type="Venue",
                   object_id=venue.id, description=f"Creó el local '{venue.name}'.")
        messages.success(request, f"Local '{venue.name}' creado. Sigue los primeros pasos para dejarlo listo.")
        return redirect("venues:detail", venue_id=venue.id)
    messages.error(request, "No se pudo crear el local. " + _errors(form))
    return redirect("venues:list")


@login_required
def venue_detail(request, venue_id):
    profile = get_or_create_profile(request.user)
    venue = get_object_or_404(Venue, pk=venue_id)
    if not (profile.is_platform_admin or (venue.is_active and user_can_access_venue(request.user, venue))):
        raise PermissionDenied("No tienes acceso a este local.")
    can_manage = user_can_manage_venue(request.user, venue)
    return render(request, "venues/detail.html", {
        "venue": venue, "s": venue_summary(venue), "can_manage": can_manage,
        "can_toggle": profile.is_platform_admin, "form": VenueForm(instance=venue) if can_manage else None,
    })


@login_required
@require_POST
def venue_edit(request, venue_id):
    venue = get_object_or_404(Venue, pk=venue_id)
    if not user_can_manage_venue(request.user, venue):
        raise PermissionDenied("No tienes permiso para editar este local.")
    form = VenueForm(request.POST, instance=venue)
    if form.is_valid():
        form.save()
        log_action(request, action=AuditLog.Action.UPDATE, module="venues", venue=venue, object_type="Venue",
                   object_id=venue.id, description=f"Editó los datos del local '{venue.name}'.")
        messages.success(request, "Datos del local actualizados.")
    else:
        messages.error(request, "No se pudo guardar. " + _errors(form))
    return redirect("venues:detail", venue_id=venue.id)


@login_required
@require_POST
def venue_toggle(request, venue_id):
    if not get_or_create_profile(request.user).is_platform_admin:
        raise PermissionDenied("Solo el administrador de la plataforma puede activar o desactivar locales.")
    venue = get_object_or_404(Venue, pk=venue_id)
    venue.is_active = not venue.is_active
    venue.save(update_fields=["is_active", "updated_at"])
    state = "activó" if venue.is_active else "desactivó"
    log_action(request, action=AuditLog.Action.UPDATE, module="venues", venue=venue, object_type="Venue",
               object_id=venue.id, description=f"{state.capitalize()} el local '{venue.name}'.")
    messages.success(request, f"Local '{venue.name}' {'activado' if venue.is_active else 'desactivado'}.")
    return redirect("venues:detail", venue_id=venue.id)