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

from .forms import DishForm, DishImageForm, MenuForm
from .models import Dish, Menu
from .services import build_dish_cards, categories_of


def _errors(form):
    return " ".join(e for errors in form.errors.values() for e in errors)


def _manageable_venues(user):
    return [v for v in Venue.objects.filter(is_active=True).order_by("name") if user_can_manage_venue(user, v)]


@login_required
def menu_list(request):
    profile = get_or_create_profile(request.user)
    available = Q(dishes__is_available=True)
    menus = (
        Menu.objects.filter(is_active=True, venue__is_active=True)
        .select_related("venue")
        .annotate(dish_count=Count("dishes", filter=available),
                  photo_count=Count("dishes", filter=available & ~Q(dishes__image="")))
    )
    if not profile.is_platform_admin:
        menus = menus.filter(venue__assigned_profiles=profile)
    items = []
    for menu in menus:
        items.append({
            "menu": menu,
            "cover": menu.dishes.exclude(image="").order_by("category", "name").first(),
            "missing": menu.dish_count - menu.photo_count,
            "photo_pct": round(100 * menu.photo_count / menu.dish_count) if menu.dish_count else 0,
            "can_manage": user_can_manage_venue(request.user, menu.venue),
        })
    dishes = sum(i["menu"].dish_count for i in items)
    photos = sum(i["menu"].photo_count for i in items)
    venues = _manageable_venues(request.user)
    return render(request, "menus/list.html", {
        "items": items,
        "totals": {"menus": len(items), "dishes": dishes, "photos": photos, "missing": dishes - photos,
                   "photo_pct": round(100 * photos / dishes) if dishes else 0},
        "menu_form": MenuForm(venues=venues) if venues else None,
    })


@login_required
@require_POST
def menu_create(request):
    venues = _manageable_venues(request.user)
    if not venues:
        raise PermissionDenied("Solo la administración del local puede crear cartas.")
    form = MenuForm(request.POST, venues=venues)
    if form.is_valid():
        menu = form.save()
        log_action(request, action=AuditLog.Action.CREATE, module="menus", venue=menu.venue,
                   object_type="Menu", object_id=menu.id, description=f"Creó la carta '{menu.name}'.")
        messages.success(request, f"Carta '{menu.name}' creada. Ahora agrega sus platos.")
        return redirect("menus:detail", menu_id=menu.id)
    messages.error(request, "No se pudo crear la carta. " + _errors(form))
    return redirect("menus:list")


@login_required
def menu_detail(request, menu_id):
    menu = get_object_or_404(
        Menu.objects.select_related("venue"), id=menu_id, is_active=True, venue__is_active=True,
    )
    if not user_can_access_venue(request.user, menu.venue):
        raise PermissionDenied("No tienes acceso a este menú.")
    can_manage = user_can_manage_venue(request.user, menu.venue)
    queryset = menu.dishes.all() if can_manage else menu.dishes.filter(is_available=True)
    dishes = list(queryset.order_by("category", "name"))
    return render(request, "menus/detail.html", {
        "menu": menu,
        "cards": build_dish_cards(dishes),
        "categories": categories_of(dishes),
        "can_manage": can_manage,
        "public_url": reverse("menus:public", args=[menu.venue_id]),
        "stats": {"total": sum(1 for d in dishes if d.is_available), "photos": sum(1 for d in dishes if d.image and d.is_available),
                  "hidden": sum(1 for d in dishes if not d.is_available)},
        "dish_form": DishForm(instance=Dish(menu=menu)) if can_manage else None,
        "edit_form": DishForm(instance=Dish(menu=menu), auto_id="edit_%s") if can_manage else None,
    })


def _managed_menu(request, menu_id):
    menu = get_object_or_404(Menu.objects.select_related("venue"), id=menu_id)
    if not user_can_manage_venue(request.user, menu.venue):
        raise PermissionDenied("No tienes permiso para modificar esta carta.")
    return menu


@login_required
@require_POST
def dish_create(request, menu_id):
    menu = _managed_menu(request, menu_id)
    form = DishForm(request.POST, request.FILES, instance=Dish(menu=menu))
    if form.is_valid():
        dish = form.save()
        log_action(request, action=AuditLog.Action.CREATE, module="menus", venue=menu.venue,
                   object_type="Dish", object_id=dish.id, description=f"Agregó el plato '{dish.name}' a '{menu.name}'.")
        messages.success(request, f"Plato '{dish.name}' agregado.")
    else:
        messages.error(request, "No se pudo agregar el plato. " + _errors(form))
    return redirect("menus:detail", menu_id=menu.id)


@login_required
@require_POST
def dish_edit(request, menu_id, dish_id):
    menu = _managed_menu(request, menu_id)
    dish = get_object_or_404(Dish, id=dish_id, menu=menu)
    form = DishForm(request.POST, request.FILES, instance=dish)
    if form.is_valid():
        form.save()
        log_action(request, action=AuditLog.Action.UPDATE, module="menus", venue=menu.venue,
                   object_type="Dish", object_id=dish.id, description=f"Editó el plato '{dish.name}'.")
        messages.success(request, f"Plato '{dish.name}' actualizado.")
    else:
        messages.error(request, "No se pudo guardar el plato. " + _errors(form))
    return redirect("menus:detail", menu_id=menu.id)


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
        messages.error(request, _errors(form))
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