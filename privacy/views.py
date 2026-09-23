from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from monitoring.models import AuditLog
from monitoring.services.audit import log_action
from authentication.permissions import (
    get_or_create_profile,
    user_can_manage_venue,
)

from venues.models import Venue

from .forms import (
    PrivacyPolicyForm,
    ProcessingAuthorizationForm,
)
from .models import PrivacyPolicy


@login_required
def policy_list(request):
    profile = get_or_create_profile(request.user)

    venues = Venue.objects.filter(
        is_active=True
    ).order_by("name")

    if not profile.is_platform_admin:
        venues = venues.filter(
            assigned_profiles=profile
        )

    venue_rows = []

    for venue in venues:
        policy = PrivacyPolicy.objects.filter(
            venue=venue
        ).prefetch_related("authorizations").first()

        venue_rows.append(
            {
                "venue": venue,
                "policy": policy,
                "is_authorized": (
                    policy.is_processing_authorized
                    if policy
                    else False
                ),
            }
        )

    return render(
        request,
        "privacy/policy_list.html",
        {"venue_rows": venue_rows},
    )


@login_required
def policy_edit(request, venue_id):
    
    venue = get_object_or_404(
        Venue,
        id=venue_id,
        is_active=True,
    )

    if not user_can_manage_venue(request.user, venue):
        raise PermissionDenied(
            "No tienes permiso para configurar privacidad en este local."
        )

    policy, _ = PrivacyPolicy.objects.get_or_create(
        venue=venue,
        defaults={
            "purpose": (
                "Generar indicadores agregados de ocupación y operación "
                "sin identificar personas ni guardar imágenes originales."
            )
        },
    )

    form = PrivacyPolicyForm(
        request.POST or None,
        instance=policy,
    )

    if request.method == "POST" and form.is_valid():
        updated_policy = form.save(commit=False)
        updated_policy.updated_by = request.user
        updated_policy.save()

        log_action(
            request,
            action=AuditLog.Action.UPDATE,
            module="privacy",
            venue=venue,
            object_type="PrivacyPolicy",
            object_id=updated_policy.id,
            description=(
                f"Actualizó política de privacidad v"
                f"{updated_policy.version} del local "
                f"'{venue.name}'. Procesamiento visual: "
                f"{'habilitado' if updated_policy.processing_enabled else 'deshabilitado'}."
            ),
        )

        messages.success(
            request,
            "La política de privacidad fue actualizada.",
        )

        return redirect(
            "privacy:policy_edit",
            venue_id=venue.id,
        )

    authorizations = policy.authorizations.select_related(
        "accepted_by"
    ).all()

    return render(
        request,
        "privacy/policy_form.html",
        {
            "venue": venue,
            "policy": policy,
            "form": form,
            "authorizations": authorizations,
        },
    )


@login_required
def authorization_create(request, venue_id):
    venue = get_object_or_404(
        Venue,
        id=venue_id,
        is_active=True,
    )

    if not user_can_manage_venue(request.user, venue):
        raise PermissionDenied(
            "No tienes permiso para registrar autorizaciones."
        )

    policy, _ = PrivacyPolicy.objects.get_or_create(
        venue=venue,
        defaults={
            "purpose": (
                "Generar indicadores agregados de ocupación y operación "
                "sin identificar personas ni guardar imágenes originales."
            )
        },
    )

    form = ProcessingAuthorizationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        authorization = form.save(commit=False)
        authorization.privacy_policy = policy
        authorization.accepted_by = request.user
        authorization.save()
        log_action(
            request,
            action=AuditLog.Action.CREATE,
            module="privacy",
            venue=venue,
            object_type="ProcessingAuthorization",
            object_id=authorization.id,
            description=(
                f"Registró autorización de procesamiento "
                f"para '{authorization.source_description}' "
                f"en el local '{venue.name}'."))
        messages.success(
            request,
            "La autorización de procesamiento fue registrada.",
        )

        return redirect(
            "privacy:policy_edit",
            venue_id=venue.id,
        )

    return render(
        request,
        "privacy/authorization_form.html",
        {
            "venue": venue,
            "policy": policy,
            "form": form,
        },
    )