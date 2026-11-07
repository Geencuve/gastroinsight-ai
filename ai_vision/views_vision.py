from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import NoReverseMatch, reverse
from django.views.decorators.http import require_POST

from analytics.views import get_accessible_venues
from authentication.permissions import get_or_create_profile
from authentication.roles import OPERATOR, PLATFORM_ADMIN, SUPERVISOR, VENUE_ADMIN, allowed_prefixes, is_path_allowed, role_key
from authentication.zones import user_zones
from cameras.models import Camera
from monitoring.models import AuditLog
from monitoring.services.audit import log_action

from .models import AnalysisSession
from .services.thumbs import camera_thumbs

TABS = [
    ("camaras", "📷 Cámaras", None),
    ("monitor", "📡 Monitor en vivo", "ai_vision:monitor"),
    ("sesiones", "🎥 Sesiones de análisis", "ai_vision:session_list"),
    ("registro", "🗂️ Registro de cámaras", "cameras:list"),
    ("entrenamiento", "🧪 Entrenamiento", "ai_vision:training"),
    ("correlacion", "📈 Correlación", "analytics:correlation"),
    ("modelo", "🧠 Cómo funciona", "vision:how_it_works"),
]
LIVE_ROLES = {PLATFORM_ADMIN, VENUE_ADMIN, SUPERVISOR, OPERATOR}


def _can_live(user, profile):
    return user.is_superuser or role_key(profile) in LIVE_ROLES


@login_required
def vision_home(request):
    profile = get_or_create_profile(request.user)
    prefixes = allowed_prefixes(profile)
    tabs = []
    for key, label, name in TABS:
        url = None
        if name:
            try:
                url = reverse(name)
            except NoReverseMatch:
                continue
            if not is_path_allowed(url, prefixes):
                continue
        if key == "entrenamiento" and not (profile.is_platform_admin or profile.is_venue_admin):
            continue
        tabs.append({"key": key, "label": label, "url": url})
    return render(request, "ai_vision/vision.html", {"tabs": tabs, "can_live": _can_live(request.user, profile)})


@login_required
def vision_data(request):
    profile = get_or_create_profile(request.user)
    items = camera_thumbs(get_accessible_venues(profile), zones=user_zones(profile))
    for item in items:
        item["live_url"] = reverse("vision:live", args=[item["id"]])
    return JsonResponse({"cameras": items})


@login_required
@require_POST
def vision_live(request, camera_id):
    profile = get_or_create_profile(request.user)
    if not _can_live(request.user, profile):
        raise PermissionDenied("Tu rol solo puede ver el esquema anónimo de las cámaras.")
    camera = get_object_or_404(Camera, pk=camera_id, venue__in=get_accessible_venues(profile))
    if camera.source_type == Camera.SourceType.DEMO:
        return JsonResponse({"available": False, "reason": "Cámara de demostración: no tiene video real."})
    if AnalysisSession.objects.filter(camera=camera, status=AnalysisSession.Status.RUNNING).exists():
        return JsonResponse({"available": False,
                             "reason": "La cámara está en análisis. La vista en vivo se habilita cuando termine "
                                       "(una webcam no puede usarse en dos procesos a la vez)."})
    log_action(request, action=AuditLog.Action.START, module="ai_vision", venue=camera.venue, object_type="Camera",
               object_id=str(camera.pk), description=f"Abrió la vista en vivo de «{camera.name}» (no se graba).")
    return JsonResponse({"available": True, "url": reverse("ai_vision:camera_preview", args=[camera.id])})


@login_required
def how_it_works(request):
    from pathlib import Path as _Path

    from django.conf import settings as _settings

    folder = _Path(_settings.BASE_DIR) / "ai_vision" / "ml_models"
    files = {p.name.lower() for p in folder.glob("*.onnx")} if folder.exists() else set()
    models = [
        {"name": "YOLO26 Small", "purpose": "Personas y mesas (escena)", "present": any("yolo" in f for f in files)},
        {"name": "YuNet", "purpose": "Detección de rostros, sin identificación", "present": any("yunet" in f or "face_detector" in f for f in files)},
        {"name": "FER+ (8 clases)", "purpose": "Clasificación de expresiones faciales", "present": any("ferplus" in f or "emotion" in f for f in files)},
    ]
    return render(request, "ai_vision/how_it_works.html", {
        "models": models, "scene_detection": getattr(_settings, "SCENE_DETECTION", True)})
