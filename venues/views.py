from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from authentication.permissions import get_or_create_profile

from .models import Venue


@login_required
def venue_list(request):
    profile = get_or_create_profile(request.user)

    if profile.is_platform_admin:
        venues = Venue.objects.filter(
            is_active=True
        )
    else:
        venues = Venue.objects.filter(
            is_active=True,
            assigned_profiles=profile,
        )

    return render(
        request,
        "venues/list.html",
        {"venues": venues},
    )