from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from authentication.permissions import get_or_create_profile

from .models import AuditLog, Incident


def can_review_incidents(profile):
    return (
        profile.is_platform_admin
        or profile.role == profile.Role.VENUE_ADMIN
    )


@login_required
def incident_list(request):
    profile = get_or_create_profile(request.user)

    incidents = Incident.objects.select_related(
        "venue",
        "reviewed_by",
    )

    if not profile.is_platform_admin:
        incidents = incidents.filter(
            venue__assigned_profiles=profile
        )

    return render(
        request,
        "monitoring/incident_list.html",
        {
            "incidents": incidents[:100],
            "can_review": can_review_incidents(profile),
        },
    )


@require_POST
@login_required
def incident_review(request, incident_id):
    profile = get_or_create_profile(request.user)

    incident = get_object_or_404(
        Incident.objects.select_related("venue"),
        id=incident_id,
    )

    if (
        not profile.is_platform_admin
        and not incident.venue.assigned_profiles.filter(
            id=profile.id
        ).exists()
    ):
        raise PermissionDenied(
            "No tienes acceso a esta incidencia."
        )

    if not can_review_incidents(profile):
        raise PermissionDenied(
            "Tu rol no puede revisar incidencias."
        )

    incident.mark_reviewed(request.user)

    messages.success(
        request,
        "La incidencia fue marcada como revisada.",
    )

    return redirect("monitoring:incident_list")


@require_POST
@login_required
def incident_resolve(request, incident_id):
    profile = get_or_create_profile(request.user)

    incident = get_object_or_404(
        Incident.objects.select_related("venue"),
        id=incident_id,
    )

    if (
        not profile.is_platform_admin
        and not incident.venue.assigned_profiles.filter(
            id=profile.id
        ).exists()
    ):
        raise PermissionDenied(
            "No tienes acceso a esta incidencia."
        )

    if not can_review_incidents(profile):
        raise PermissionDenied(
            "Tu rol no puede resolver incidencias."
        )

    incident.mark_resolved(request.user)

    messages.success(
        request,
        "La incidencia fue marcada como resuelta.",
    )

    return redirect("monitoring:incident_list")


@login_required
def audit_log_list(request):
    profile = get_or_create_profile(request.user)

    if not profile.is_platform_admin:
        raise PermissionDenied(
            "Solo el administrador de plataforma puede consultar la auditoría."
        )

    logs = AuditLog.objects.select_related(
        "user",
        "venue",
    )[:200]

    return render(
        request,
        "monitoring/audit_log_list.html",
        {"logs": logs},
    )
