from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from analytics.views import get_accessible_venues
from authentication.models import Profile
from authentication.permissions import get_or_create_profile
from cameras.models import Camera

from .models import AnalysisSession
from .services.launcher import launch_simulation
from .services.live import build_live_state


def _venues(request):
    return get_accessible_venues(get_or_create_profile(request.user))


@login_required
def monitor(request):
    profile = get_or_create_profile(request.user)
    can_operate = profile.is_platform_admin or profile.is_venue_admin or profile.role == Profile.Role.OPERATOR
    simulating = AnalysisSession.objects.filter(
        camera__source_type=Camera.SourceType.DEMO, status=AnalysisSession.Status.RUNNING,
    ).exists()
    return render(request, "ai_vision/monitor.html", {"can_operate": can_operate, "simulating": simulating})


@login_required
def monitor_data(request):
    return JsonResponse(build_live_state(_venues(request)))


@login_required
@require_POST
def monitor_simulate(request):
    profile = get_or_create_profile(request.user)
    if not (profile.is_platform_admin or profile.is_venue_admin or profile.role == Profile.Role.OPERATOR):
        messages.error(request, "Tu rol no permite iniciar la simulación.")
    elif AnalysisSession.objects.filter(
        camera__source_type=Camera.SourceType.DEMO, status=AnalysisSession.Status.RUNNING,
    ).exists():
        messages.info(request, "La simulación de mesas demo ya está en curso.")
    else:
        launch_simulation(minutes=10)
        messages.success(request, "Simulación de mesas demo iniciada por 10 minutos (datos sintéticos).")
    return redirect("ai_vision:monitor")
