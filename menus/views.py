from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from authentication.permissions import (
    get_or_create_profile,
    user_can_access_venue,
    user_can_manage_venue,
)
from monitoring.models import AuditLog
from monitoring.services.audit import log_action
from venues.models import Venue

from .forms import DishImageForm
from .models import Dish, Menu
from .services import build_dish_cards, categories_of


@login_required
def menu_list(request):
    profile = get_or_create_profile(request.user)
    menus = (
        Menu.objects.filter(is_active=True, venue__is_active=True)
        .select_related("venue")
        .annotate(dish_count=Count("dishes", filter=Q(dishes__is_available=True)))
    )
    if not profile.is_platform_admin:
        menus = menus.filter(venue__assigned_profiles=profile)
    items = [
        {"menu": menu, "cover": menu.dishes.exclude(image="").order_by("category", "name").first()}
        for menu in menus
    ]
    return render(request, "menus/list.html", {"items": items})


@login_required
def menu_detail(request, menu_id):
    menu = get_object_or_404(
        Menu.objects.select_related("venue"), id=menu_id, is_active=True, venue__is_active=True,
    )
    if not user_can_access_venue(request.user, menu.venue):
        raise PermissionDenied("No tienes acceso a este menú.")
    dishes = list(menu.dishes.filter(is_available=True).order_by("category", "name"))
    return render(request, "menus/detail.html", {
        "menu": menu,
        "cards": build_dish_cards(dishes),
        "categories": categories_of(dishes),
        "can_manage": user_can_manage_venue(request.user, menu.venue),
        "public_url": reverse("menus:public", args=[menu.venue_id]),
    })


@login_required
@require_POST
def dish_image_update(request, menu_id, dish_id):
    dish = get_object_or_404(Dish.objects.select_related("menu__venue"), id=dish_id, menu_id=menu_id)
    if not user_can_manage_venue(request.user, dish.menu.venue):
        raise PermissionDenied("No tienes permiso para modificar este plato.")
    form = DishImageForm(request.POST, request.FILES, instance=dish)
    if form.is_valid():
        form.save()
        log_action(
            request, action=AuditLog.Action.UPDATE, module="menus", venue=dish.menu.venue,
            object_type="Dish", object_id=dish.id, description=f"Actualizó la foto del plato '{dish.name}'.",
        )
        messages.success(request, f"Foto de '{dish.name}' actualizada.")
    else:
        messages.error(request, " ".join(e for errors in form.errors.values() for e in errors))
    return redirect("menus:detail", menu_id=menu_id)


def public_menu(request, venue_id):
    """Carta pública del local: no requiere iniciar sesión."""
    venue = get_object_or_404(Venue, id=venue_id, is_active=True)
    dishes = list(
        Dish.objects.filter(menu__venue=venue, menu__is_active=True, is_available=True)
        .select_related("menu").order_by("category", "name")
    )
    return render(request, "menus/public.html", {
        "venue": venue, "cards": build_dish_cards(dishes), "categories": categories_of(dishes),
    })
