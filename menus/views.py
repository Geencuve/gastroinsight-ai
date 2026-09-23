from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from authentication.permissions import (
    get_or_create_profile,
    user_can_access_venue,
)

from .models import Menu


@login_required
def menu_list(request):
    profile = get_or_create_profile(request.user)

    menus = Menu.objects.filter(
        is_active=True,
        venue__is_active=True,
    ).select_related("venue")

    if not profile.is_platform_admin:
        menus = menus.filter(
            venue__assigned_profiles=profile
        )

    return render(
        request,
        "menus/list.html",
        {"menus": menus},
    )


@login_required
def menu_detail(request, menu_id):
    menu = get_object_or_404(
        Menu.objects.select_related("venue"),
        id=menu_id,
        is_active=True,
        venue__is_active=True,
    )

    if not user_can_access_venue(request.user, menu.venue):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied(
            "No tienes acceso a este menú."
        )

    dishes = menu.dishes.filter(
        is_available=True
    )

    return render(
        request,
        "menus/detail.html",
        {
            "menu": menu,
            "dishes": dishes,
        },
    )