from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import Profile


def get_or_create_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def user_can_access_venue(user, venue):
    if not user.is_authenticated:
        return False

    profile = get_or_create_profile(user)

    return profile.is_platform_admin or profile.venues.filter(
        id=venue.id
    ).exists()


def user_can_manage_venue(user, venue):
    if not user_can_access_venue(user, venue):
        return False

    profile = get_or_create_profile(user)

    return profile.is_platform_admin or profile.is_venue_admin


def user_can_operate_camera(user, venue):
    if not user_can_access_venue(user, venue):
        return False

    profile = get_or_create_profile(user)

    return (
        profile.is_platform_admin
        or profile.is_venue_admin
        or profile.role == Profile.Role.OPERATOR
    )


def venue_access_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        venue = kwargs.get("venue")

        if venue is None:
            raise PermissionDenied(
                "La vista debe recibir un local para validar acceso."
            )

        if not user_can_access_venue(request.user, venue):
            messages.error(
                request,
                "No tienes permiso para acceder a este local.",
            )
            return redirect("venues:list")

        return view_func(request, *args, **kwargs)

    return wrapped_view