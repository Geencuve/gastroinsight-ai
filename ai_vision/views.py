import cv2

from django.http import StreamingHttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from monitoring.models import AuditLog
from monitoring.services.audit import log_action
from authentication.models import Profile
from authentication.permissions import (
    get_or_create_profile,
    user_can_access_venue,
    user_can_operate_camera,
)
from cameras.models import Camera

from .models import AnalysisSession


@login_required
def session_list(request):
    profile = get_or_create_profile(request.user)

    cameras = (
        Camera.objects.filter(
            is_active=True,
            venue__is_active=True,
        )
        .select_related("venue")
        .order_by("venue__name", "name")
    )

    sessions = (
        AnalysisSession.objects.select_related(
            "camera",
            "camera__venue",
        )
        .order_by("-created_at")
    )

    if not profile.is_platform_admin:
        cameras = cameras.filter(
            venue__assigned_profiles=profile
        )
        sessions = sessions.filter(
            camera__venue__assigned_profiles=profile
        )

    can_operate = (
        profile.is_platform_admin
        or profile.is_venue_admin
        or profile.role == Profile.Role.OPERATOR
    )

    return render(
        request,
        "ai_vision/session_list.html",
        {
            "cameras": cameras,
            "sessions": sessions[:25],
            "can_operate": can_operate,
        },
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
        raise PermissionDenied(
            "No tienes permiso para crear sesiones en esta cámara."
        )

    with transaction.atomic():
        active_session = (
            AnalysisSession.objects.select_for_update()
            .filter(
                camera=camera,
                status__in=[
                    AnalysisSession.Status.PENDING,
                    AnalysisSession.Status.RUNNING,
                ],
            )
            .first()
        )

        if active_session:
            messages.warning(
                request,
                (
                    f"La cámara '{camera.name}' ya tiene "
                    f"una sesión activa (#{active_session.id})."
                ),
            )
        else:
            session = AnalysisSession.objects.create(
                camera=camera,
                status=AnalysisSession.Status.PENDING,
            )
            log_action(
                request,
                action=AuditLog.Action.CREATE,
                module="ai_vision",
                venue=camera.venue,
                object_type="AnalysisSession",
                object_id=session.id,
                description=(
                    f"Creó sesión de análisis #{session.id} "
                    f"para cámara '{camera.name}'."
                ),
)
            messages.success(
                request,
                (
                    f"Sesión #{session.id} creada para "
                    f"la cámara '{camera.name}'."
                ),
            )

    return redirect("ai_vision:session_list")


@require_POST
@login_required
def start_session(request, session_id):
    session = get_object_or_404(
        AnalysisSession.objects.select_related(
            "camera",
            "camera__venue",
        ),
        id=session_id,
    )

    if not user_can_operate_camera(
        request.user,
        session.camera.venue,
    ):
        raise PermissionDenied(
            "No tienes permiso para iniciar esta sesión."
        )

    if session.status != AnalysisSession.Status.PENDING:
        messages.warning(
            request,
            "Solo se pueden iniciar sesiones pendientes.",
        )
        return redirect("ai_vision:session_list")

    session.start()

    log_action(
        request,
        action=AuditLog.Action.START,
        module="ai_vision",
        venue=session.camera.venue,
        object_type="AnalysisSession",
        object_id=session.id,
        description=(
            f"Inició sesión de análisis #{session.id} "
            f"de la cámara '{session.camera.name}'."
        ),
    )

    messages.success(
        request,
        (
            f"Sesión #{session.id} marcada como En ejecución. "
            "Ejecuta el comando de cámara desde la terminal."
        ),
    )

    return redirect("ai_vision:session_list")


@require_POST
@login_required
def stop_session(request, session_id):
    session = get_object_or_404(
        AnalysisSession.objects.select_related(
            "camera",
            "camera__venue",
        ),
        id=session_id,
    )

    if not user_can_operate_camera(
        request.user,
        session.camera.venue,
    ):
        raise PermissionDenied(
            "No tienes permiso para detener esta sesión."
        )

    if session.status != AnalysisSession.Status.RUNNING:
        messages.warning(
            request,
            "Solo se pueden detener sesiones en ejecución.",
        )
        return redirect("ai_vision:session_list")

    session.finish(
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
            f"Detuvo sesión de análisis #{session.id} "
            f"de la cámara '{session.camera.name}'."
        ),
    )
    messages.success(
        request,
        f"Sesión #{session.id} fue detenida.",
    )

    return redirect("ai_vision:session_list")


@login_required
def session_detail(request, session_id):
    """
    Muestra el detalle de una sesión de análisis:
    cámara, estado, fechas y métricas disponibles.
    """
    session = get_object_or_404(
        AnalysisSession.objects.select_related(
            "camera",
            "camera__venue",
        ),
        id=session_id,
    )

    if not user_can_access_venue(
        request.user,
        session.camera.venue,
    ):
        raise PermissionDenied(
            "No tienes permiso para ver esta sesión."
        )

    profile = get_or_create_profile(request.user)

    can_operate = (
        profile.is_platform_admin
        or profile.is_venue_admin
        or profile.role == Profile.Role.OPERATOR
    )

    return render(
        request,
        "ai_vision/session_detail.html",
        {
            "session": session,
            "camera": session.camera,
            "can_operate": can_operate,
        },
    )

def get_camera_source(camera):
    """
    Obtiene el origen de video configurado para una cámara.

    Acepta webcam local (por ejemplo '0') o una URL RTSP/HTTP.
    """
    source = getattr(camera, "stream_url", None)

    if not source:
        source = getattr(camera, "url", None)

    if source is None or source == "":
        return 0

    source = str(source).strip()

    if source.isdigit():
        return int(source)

    return source


def generate_camera_frames(camera):
    """
    Abre la cámara y entrega frames JPEG en formato MJPEG.

    Cada fragmento que entrega esta función es interpretado por el
    navegador como una nueva imagen dentro del stream.
    """
    source = get_camera_source(camera)

    if isinstance(source, int):
        capture = cv2.VideoCapture(source, cv2.CAP_DSHOW)
    else:
        capture = cv2.VideoCapture(source)

    if not capture.isOpened():
        raise RuntimeError(
            f"No fue posible abrir la cámara '{camera.name}'."
        )

    try:
        while True:
            success, frame = capture.read()

            if not success:
                break

            success, buffer = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), 80],
            )

            if not success:
                continue

            frame_bytes = buffer.tobytes()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame_bytes
                + b"\r\n"
            )

    finally:
        capture.release()


@login_required
def camera_preview(request, camera_id):
    """
    Endpoint de streaming MJPEG para visualizar una cámara desde el navegador.
    """
    camera = get_object_or_404(
        Camera.objects.select_related("venue"),
        id=camera_id,
        is_active=True,
        venue__is_active=True,
    )

    if not user_can_access_venue(
        request.user,
        camera.venue,
    ):
        raise PermissionDenied(
            "No tienes permiso para visualizar esta cámara."
        )

    return StreamingHttpResponse(
        generate_camera_frames(camera),
        content_type=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        ),
    )