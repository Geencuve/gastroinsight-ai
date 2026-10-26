import cv2
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import close_old_connections, transaction
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from authentication.models import Profile
from authentication.permissions import (
    get_or_create_profile,
    user_can_access_venue,
    user_can_operate_camera,
)
from cameras.models import Camera
from monitoring.models import AuditLog
from monitoring.services.audit import log_action
from privacy.models import PrivacyPolicy

from .models import AnalysisSession


@login_required
def session_list(request):
    profile = get_or_create_profile(request.user)
    cameras = (
        Camera.objects.filter(is_active=True, venue__is_active=True)
        .select_related("venue")
        .order_by("venue__name", "name")
    )
    sessions = (
        AnalysisSession.objects.select_related("camera", "camera__venue")
        .order_by("-created_at")
    )

    if not profile.is_platform_admin:
        cameras = cameras.filter(venue__assigned_profiles=profile)
        sessions = sessions.filter(camera__venue__assigned_profiles=profile)

    can_operate = (
        profile.is_platform_admin
        or profile.is_venue_admin
        or profile.role == Profile.Role.OPERATOR
    )
    return render(
        request,
        "ai_vision/session_list.html",
        {"cameras": cameras, "sessions": sessions[:25], "can_operate": can_operate},
    )


@require_POST
@login_required
def create_session(request, camera_id):
    camera = get_object_or_404(
        Camera.objects.select_related("venue"),
        id=camera_id,
        is_active=True,
        venue__is_active=True,
    )
    if not user_can_operate_camera(request.user, camera.venue):
        raise PermissionDenied("No tienes permiso para crear sesiones en esta cámara.")

    with transaction.atomic():
        # Bloquear la cámara serializa la creación de sesiones para esa cámara.
        camera = Camera.objects.select_for_update().get(pk=camera.pk)
        active_session = (
            AnalysisSession.objects.filter(
                camera=camera,
                status__in=[AnalysisSession.Status.PENDING, AnalysisSession.Status.RUNNING],
            )
            .order_by("pk")
            .first()
        )
        if active_session:
            messages.warning(
                request,
                f"La cámara '{camera.name}' ya tiene una sesión activa (#{active_session.id}).",
            )
        else:
            session = AnalysisSession.objects.create(
                camera=camera, status=AnalysisSession.Status.PENDING
            )
            log_action(
                request,
                action=AuditLog.Action.CREATE,
                module="ai_vision",
                venue=camera.venue,
                object_type="AnalysisSession",
                object_id=session.id,
                description=(
                    f"Creó sesión de análisis #{session.id} para cámara '{camera.name}'."
                ),
            )
            messages.success(
                request, f"Sesión #{session.id} creada para la cámara '{camera.name}'."
            )
    return redirect("ai_vision:session_list")


@require_POST
@login_required
def start_session(request, session_id):
    session = get_object_or_404(
        AnalysisSession.objects.select_related("camera", "camera__venue"),
        id=session_id,
    )
    if not user_can_operate_camera(request.user, session.camera.venue):
        raise PermissionDenied("No tienes permiso para iniciar esta sesión.")
    if session.status != AnalysisSession.Status.PENDING:
        messages.warning(request, "Solo se pueden iniciar sesiones pendientes.")
    else:
        messages.info(
            request,
            (
                f"Sesión #{session.id} preparada. Ejecuta en la terminal: "
                f"python manage.py run_camera_analysis {session.id} --no-preview"
            ),
        )
    return redirect("ai_vision:session_list")


@require_POST
@login_required
def stop_session(request, session_id):
    session = get_object_or_404(
        AnalysisSession.objects.select_related("camera", "camera__venue"),
        id=session_id,
    )
    if not user_can_operate_camera(request.user, session.camera.venue):
        raise PermissionDenied("No tienes permiso para detener esta sesión.")

    with transaction.atomic():
        locked = AnalysisSession.objects.select_for_update().get(pk=session.pk)
        if locked.status != AnalysisSession.Status.RUNNING:
            messages.warning(request, "Solo se pueden detener sesiones en ejecución.")
        else:
            locked.finish(
                status=AnalysisSession.Status.STOPPED,
                error_message="Sesión detenida manualmente desde la interfaz.",
            )
            log_action(
                request,
                action=AuditLog.Action.STOP,
                module="ai_vision",
                venue=session.camera.venue,
                object_type="AnalysisSession",
                object_id=session.id,
                description=(
                    f"Solicitó detener la sesión de análisis #{session.id} "
                    f"de la cámara '{session.camera.name}'."
                ),
            )
            messages.success(
                request,
                f"Se solicitó detener la sesión #{session.id}; "
                "la captura se cerrará al siguiente ciclo de lectura.",
            )
    return redirect("ai_vision:session_list")


@login_required
def session_detail(request, session_id):
    session = get_object_or_404(
        AnalysisSession.objects.select_related("camera", "camera__venue"),
        id=session_id,
    )
    if not user_can_access_venue(request.user, session.camera.venue):
        raise PermissionDenied("No tienes permiso para ver esta sesión.")
    profile = get_or_create_profile(request.user)
    can_operate = (
        profile.is_platform_admin
        or profile.is_venue_admin
        or profile.role == Profile.Role.OPERATOR
    )
    return render(
        request,
        "ai_vision/session_detail.html",
        {"session": session, "camera": session.camera, "can_operate": can_operate},
    )


def get_camera_source(camera):
    source = camera.source
    if source is None or not str(source).strip():
        raise RuntimeError(f"La cámara '{camera.name}' no tiene un origen configurado.")
    source = str(source).strip()
    if camera.source_type == Camera.SourceType.WEBCAM:
        if not source.isdigit():
            raise RuntimeError("El origen de la webcam debe ser un índice numérico.")
        return int(source)
    return source


def generate_camera_frames(camera):
    source = get_camera_source(camera)
    if camera.source_type == Camera.SourceType.WEBCAM:
        capture = cv2.VideoCapture(source, cv2.CAP_DSHOW)
    else:
        capture = cv2.VideoCapture(source)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"No fue posible abrir la cámara '{camera.name}'.")
    try:
        while True:
            close_old_connections()
            try:
                policy = PrivacyPolicy.objects.get(venue_id=camera.venue_id)
            except PrivacyPolicy.DoesNotExist:
                break
            if not policy.is_processing_authorized:
                break
            if not Camera.objects.filter(
                pk=camera.pk, is_active=True, venue__is_active=True
            ).exists():
                break
            success, frame = capture.read()
            if not success:
                break
            success, buffer = cv2.imencode(
                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            )
            if not success:
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buffer.tobytes()
                + b"\r\n"
            )
    finally:
        capture.release()
        close_old_connections()


@login_required
def camera_preview(request, camera_id):
    camera = get_object_or_404(
        Camera.objects.select_related("venue"),
        id=camera_id,
        is_active=True,
        venue__is_active=True,
    )
    if not user_can_access_venue(request.user, camera.venue):
        raise PermissionDenied("No tienes permiso para visualizar esta cámara.")
    try:
        policy = camera.venue.privacy_policy
    except PrivacyPolicy.DoesNotExist as exc:
        raise PermissionDenied(
            "No hay política de privacidad configurada para este local."
        ) from exc
    if not policy.is_processing_authorized:
        raise PermissionDenied(
            "La visualización está bloqueada por la política de privacidad del local."
        )
    return StreamingHttpResponse(
        generate_camera_frames(camera),
        content_type="multipart/x-mixed-replace; boundary=frame",
    )