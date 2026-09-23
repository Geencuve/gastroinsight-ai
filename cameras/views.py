from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from authentication.permissions import get_or_create_profile

from .models import Camera


@login_required
def camera_list(request):
    profile = get_or_create_profile(request.user)

    cameras = Camera.objects.filter(
        is_active=True,
        venue__is_active=True,
    ).select_related("venue")

    if not profile.is_platform_admin:
        cameras = cameras.filter(
            venue__assigned_profiles=profile
        )

    return render(
        request,
        "cameras/list.html",
        {"cameras": cameras},
    )