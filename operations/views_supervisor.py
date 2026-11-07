from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from analytics.views import get_accessible_venues
from authentication.models import Profile
from authentication.permissions import get_or_create_profile

from .models import EnvironmentReading, InfrastructureReport
from .services.supervisor import build_supervisor


def _venues(request):
    return get_accessible_venues(get_or_create_profile(request.user))


def _venue_from_post(request):
    venues = _venues(request)
    return venues.filter(pk=request.POST.get("venue")).first() or venues.first()


def _require_staff(request):
    if get_or_create_profile(request.user).role in (Profile.Role.VIEWER, Profile.Role.KITCHEN, Profile.Role.BAR):
        raise PermissionDenied("Tu rol no puede registrar información del local.")


def _score(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= 5 else None


@login_required
def dashboard(request):
    from ai_vision.services.camera_metrics import camera_measurements
    from authentication.zones import user_zones

    venues = _venues(request)
    context = build_supervisor(venues)
    zones = user_zones(get_or_create_profile(request.user))
    if zones is not None:
        context["cameras"] = camera_measurements(venues, zones=zones)
    context["kpis"]["cameras_live"] = sum(1 for c in context["cameras"] if c["live"])
    return render(request, "operations/supervisor.html", context)


@login_required
@require_POST
def add_environment(request):
    _require_staff(request)
    venue = _venue_from_post(request)
    try:
        temperature = Decimal(request.POST.get("temperature_c", "").replace(",", ".")) if request.POST.get("temperature_c") else None
    except InvalidOperation:
        temperature = None
    EnvironmentReading.objects.create(
        venue=venue, zone=(request.POST.get("zone") or "Salón principal").strip()[:80],
        lighting=_score(request.POST.get("lighting")), noise=_score(request.POST.get("noise")),
        temperature_c=temperature, notes=(request.POST.get("notes") or "").strip()[:200], recorded_by=request.user,
    )
    messages.success(request, "Condiciones ambientales registradas.")
    return redirect("supervisor:home")


@login_required
@require_POST
def add_report(request):
    _require_staff(request)
    area = request.POST.get("area")
    description = (request.POST.get("description") or "").strip()[:255]
    if area not in InfrastructureReport.Area.values or not description:
        messages.error(request, "Indica el área y una descripción.")
        return redirect("supervisor:home")
    InfrastructureReport.objects.create(venue=_venue_from_post(request), area=area, description=description,
                                        reported_by=request.user)
    messages.success(request, "Reporte de infraestructura registrado.")
    return redirect("supervisor:home")


@login_required
@require_POST
def resolve_report(request, report_id):
    _require_staff(request)
    report = get_object_or_404(InfrastructureReport, pk=report_id, venue__in=_venues(request))
    report.status, report.resolved_at = "resolved", timezone.now()
    report.save(update_fields=["status", "resolved_at"])
    messages.success(request, "Reporte marcado como resuelto.")
    return redirect("supervisor:home")
