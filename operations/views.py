from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .forms import (
    RestaurantTableForm,
    SatisfactionEvaluationForm,
    ServiceSessionForm,
)
from authentication.permissions import (
    get_or_create_profile,
    user_can_access_venue,
    user_can_manage_venue,
)
from monitoring.models import AuditLog
from monitoring.services.audit import log_action
from venues.models import Venue
from operations.models import SatisfactionEvaluation
from .forms import RestaurantTableForm, ServiceSessionForm
from .models import RestaurantTable, ServiceSession


@login_required
def table_list(request):
    profile = get_or_create_profile(request.user)

    tables = RestaurantTable.objects.select_related(
        "venue"
    ).order_by(
        "venue__name",
        "code",
    )

    venues = Venue.objects.filter(
        is_active=True
    ).order_by("name")

    if not profile.is_platform_admin:
        tables = tables.filter(
            venue__assigned_profiles=profile
        )
        venues = venues.filter(
            assigned_profiles=profile
        )

    return render(
        request,
        "operations/table_list.html",
        {
            "tables": tables,
            "venues": venues,
            "can_manage": (
                profile.is_platform_admin
                or profile.is_venue_admin
            ),
        },
    )


@login_required
def table_create(request, venue_id):
    venue = get_object_or_404(
        Venue,
        id=venue_id,
        is_active=True,
    )

    if not user_can_manage_venue(request.user, venue):
        raise PermissionDenied(
            "No tienes permiso para crear mesas en este local."
        )

    form = RestaurantTableForm(
        request.POST or None,
        venue=venue,
    )

    if request.method == "POST" and form.is_valid():
        table = form.save(commit=False)
        table.venue = venue
        table.save()

        messages.success(
            request,
            f"Mesa '{table.code}' creada correctamente.",
        )

        return redirect("operations:table_list")

    return render(
        request,
        "operations/table_form.html",
        {
            "form": form,
            "venue": venue,
        },
    )


@login_required
def service_session_list(request):
    profile = get_or_create_profile(request.user)

    sessions = ServiceSession.objects.select_related(
        "table",
        "table__venue",
        "created_by",
        "closed_by",
    ).order_by("-started_at")

    venues = Venue.objects.filter(
        is_active=True
    ).order_by("name")

    if not profile.is_platform_admin:
        sessions = sessions.filter(
            table__venue__assigned_profiles=profile
        )
        venues = venues.filter(
            assigned_profiles=profile
        )

    can_operate = (
        profile.is_platform_admin
        or profile.is_venue_admin
        or profile.role == profile.Role.OPERATOR
    )

    return render(
        request,
        "operations/session_list.html",
        {
            "sessions": sessions[:50],
            "venues": venues,
            "can_operate": can_operate,
        },
    )

@login_required
def service_session_create(request):
    profile = get_or_create_profile(request.user)

    venues = Venue.objects.filter(
        is_active=True
    )

    if not profile.is_platform_admin:
        venues = venues.filter(
            assigned_profiles=profile
        )

    can_operate = (
        profile.is_platform_admin
        or profile.is_venue_admin
        or profile.role == profile.Role.OPERATOR
    )

    if not can_operate:
        raise PermissionDenied(
            "Tu rol no permite abrir sesiones de atención."
        )

    form = ServiceSessionForm(
        request.POST or None,
        venues=venues,
    )

    if request.method == "POST" and form.is_valid():
        table = form.cleaned_data["table"]

        if not user_can_access_venue(request.user, table.venue):
            raise PermissionDenied(
                "No tienes acceso a la mesa seleccionada."
            )

        try:
            with transaction.atomic():
                session = form.save(commit=False)
                session.created_by = request.user
                session.save()

        except IntegrityError:
            form.add_error(
                "table",
                "La mesa ya tiene una sesión abierta.",
            )
        else:
            messages.success(
                request,
                (
                    f"Sesión de atención #{session.id} iniciada "
                    f"en la mesa {session.table.code}."
                ),
            )
            return redirect("operations:session_list")

    return render(
        request,
        "operations/session_form.html",
        {"form": form},
    )


@require_POST
@login_required
def service_session_close(request, session_id):
    service_session = get_object_or_404(
        ServiceSession.objects.select_related(
            "table",
            "table__venue",
        ),
        id=session_id,
    )

    if not user_can_access_venue(
        request.user,
        service_session.table.venue,
    ):
        raise PermissionDenied(
            "No tienes permiso para cerrar esta sesión."
        )

    if service_session.close(user=request.user):
        log_action(
            request,
            action=AuditLog.Action.STOP,
            module="operations",
            venue=service_session.table.venue,
            object_type="ServiceSession",
            object_id=service_session.id,
            description=(
                f"Cerró sesión de atención #{service_session.id} "
                f"en mesa {service_session.table.code}."
            ),
        )

        messages.success(
            request,
            f"Sesión #{service_session.id} cerrada correctamente.",
        )
    
    else:
        messages.warning(
            request,
            "La sesión no está abierta o ya fue cerrada.",
        )

    return redirect("operations:session_list")


@require_POST
@login_required
def service_session_cancel(request, session_id):
    log_action(
    request,
    action=AuditLog.Action.STOP,
    module="operations",
    venue=service_session.table.venue,
    object_type="ServiceSession",
    object_id=service_session.id,
    description=(
        f"Canceló sesión de atención #{service_session.id} "
        f"en mesa {service_session.table.code}."
    ),
)
    service_session = get_object_or_404(
        ServiceSession.objects.select_related(
            "table",
            "table__venue",
        ),
        id=session_id,
    )

    if not user_can_manage_venue(
        request.user,
        service_session.table.venue,
    ):
        raise PermissionDenied(
            "No tienes permiso para cancelar esta sesión."
        )

    if service_session.cancel(user=request.user):
        messages.success(
            request,
            f"Sesión #{service_session.id} cancelada.",
        )
    else:
        messages.warning(
            request,
            "La sesión no está abierta o ya fue finalizada.",
        )

    return redirect("operations:session_list")

@login_required
def evaluation_list(request):
    profile = get_or_create_profile(request.user)

    evaluations = (
        SatisfactionEvaluation.objects.select_related(
            "service_session",
            "service_session__table",
            "service_session__table__venue",
            "dish",
            "dish__menu",
            "registered_by",
        )
        .order_by("-created_at")
    )

    venues = Venue.objects.filter(
        is_active=True
    ).order_by("name")

    if not profile.is_platform_admin:
        evaluations = evaluations.filter(
            service_session__table__venue__assigned_profiles=profile
        )
        venues = venues.filter(
            assigned_profiles=profile
        )

    can_register = (
        profile.is_platform_admin
        or profile.is_venue_admin
        or profile.role == profile.Role.OPERATOR
    )

    return render(
        request,
        "operations/evaluation_list.html",
        {
            "evaluations": evaluations[:50],
            "venues": venues,
            "can_register": can_register,
        },
    )


@login_required
def evaluation_create(request):
    profile = get_or_create_profile(request.user)

    venues = Venue.objects.filter(
        is_active=True
    )

    if not profile.is_platform_admin:
        venues = venues.filter(
            assigned_profiles=profile
        )

    can_register = (
        profile.is_platform_admin
        or profile.is_venue_admin
        or profile.role == profile.Role.OPERATOR
    )

    if not can_register:
        raise PermissionDenied(
            "Tu rol no permite registrar evaluaciones."
        )

    form = SatisfactionEvaluationForm(
        request.POST or None,
        venues=venues,
    )

    if request.method == "POST" and form.is_valid():
        evaluation = form.save(commit=False)

        if not user_can_access_venue(
            request.user,
            evaluation.service_session.table.venue,
        ):
            raise PermissionDenied(
                "No tienes acceso al local de la sesión seleccionada."
            )

        evaluation.registered_by = request.user

        try:
            evaluation.full_clean()
            evaluation.save()
        except ValidationError as error:
            for field, errors in error.message_dict.items():
                for message in errors:
                    form.add_error(field, message)
        else:
            log_action(
                    request,
                    action=AuditLog.Action.CREATE,
                    module="operations",
                    venue=evaluation.service_session.table.venue,
                    object_type="SatisfactionEvaluation",
                    object_id=evaluation.id,
                    description=(
                        f"Registró evaluación voluntaria #{evaluation.id} "
                        f"para sesión de atención "
                        f"#{evaluation.service_session_id}."
                    ),
                )
            messages.success(
                request,
                "Evaluación voluntaria registrada correctamente.",
            )
            return redirect("operations:evaluation_list")

    return render(
        request,
        "operations/evaluation_form.html",
        {"form": form},
    )