

@login_required
def api_tutorial(request):
    """Tutorial paso a paso de la API de integración, con ejemplos armados con los datos reales del local."""
    from menus.models import Dish
    from operations.models import ApiKey

    _, venues = _actor(request)
    tables = list(RestaurantTable.objects.filter(venue__in=venues).order_by("code").values_list("code", flat=True)[:12])
    dishes = list(Dish.objects.filter(menu__venue__in=venues).order_by("name").values_list("name", flat=True)[:2])
    cameras = Camera.objects.filter(venue__in=venues).select_related("table", "venue").order_by("pk")
    return render(request, "authentication/management/api_tutorial.html", {
        "api_base": request.build_absolute_uri("/api/v1/"),
        "venues_list": venues,
        "cameras": cameras,
        "tables": tables,
        "example_table": tables[0] if tables else "M01",
        "example_dish": dishes[0] if dishes else "Lomo vetado con papas rústicas",
        "example_dish_2": dishes[1] if len(dishes) > 1 else "",
        "example_camera": cameras[0].pk if cameras else 1,
        "active_keys": ApiKey.objects.filter(venue__in=venues, is_active=True).count(),
        "payment_methods": ["efectivo", "débito", "crédito", "transferencia", "otro"],
    })
