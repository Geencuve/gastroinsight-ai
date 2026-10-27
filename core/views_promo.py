from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse

from analytics.views import get_accessible_venues
from authentication.permissions import get_or_create_profile
from menus.models import Dish
from menus.services import sort_dishes
from monitoring.models import AuditLog
from monitoring.services.audit import log_action

from .services.insights import clp
from .services.promo_images import build_caption, render_promo

WEEKDAYS = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]
PROMO_TYPES = [
    ("estrella", "⭐ Plato estrella"),
    ("combo", "🤝 Combo"),
    ("dia", "📅 Día especial"),
    ("joya", "💎 Sugerencia del chef"),
    ("happy", "🍹 Happy hour"),
    ("libre", "✏️ Libre"),
]
DEFAULTS = {
    "estrella": ("PLATO ESTRELLA", "El favorito de nuestros clientes"),
    "combo": ("COMBO", "Pídelos juntos y ahorra"),
    "dia": ("{dia} ESPECIAL", "2x1 en bebidas todo el día"),
    "joya": ("SUGERENCIA DEL CHEF", "Nuestro secreto mejor guardado"),
    "happy": ("HAPPY HOUR", "De 16:00 a 19:00 a precio especial"),
    "libre": ("PROMOCIÓN", ""),
}


def _dishes_for(request):
    venues = get_accessible_venues(get_or_create_profile(request.user))
    dishes = Dish.objects.filter(
        menu__venue__in=venues, menu__is_active=True, is_available=True,
    ).select_related("menu__venue")
    return venues, sort_dishes(list(dishes))


def _int(value, default=None):
    try:
        return int(str(value).replace(".", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return default


def resolve_promo(params, venues, dishes):
    """Completa los parámetros con valores por defecto según el tipo de promoción."""
    types = dict(PROMO_TYPES)
    kind = params.get("tipo") if params.get("tipo") in types else "estrella"
    by_id = {dish.id: dish for dish in dishes}
    dish = by_id.get(_int(params.get("plato"))) or (dishes[0] if dishes else None)
    second = by_id.get(_int(params.get("plato2")))
    if kind == "combo" and second is None:
        second = next((d for d in dishes if d.category == "Bebida" and d != dish), None)
    day = min(max(_int(params.get("dia"), 1), 0), 6)

    headline_default, offer_default = DEFAULTS[kind]
    headline = (params.get("titular") or headline_default.format(dia=WEEKDAYS[day]))[:40]
    if kind == "combo" and dish and second:
        title_default = f"{dish.name} + {second.name}"
    else:
        title_default = dish.name if dish else "Nuestra carta"
    title = (params.get("titulo") or title_default)[:60]
    offer = (params.get("oferta") if params.get("oferta") is not None else offer_default)[:90]

    old_price_value = None
    price_value = _int(params.get("precio"))
    if price_value is None and dish:
        if kind == "combo" and second:
            old_price_value = int(dish.price + second.price)
            price_value = int(old_price_value * 0.9 // 100 * 100 - 10)
        else:
            price_value = int(dish.price)
    story = params.get("formato") == "historia"
    venue = dish.menu.venue if dish else venues.first()

    query = {
        "tipo": kind, "plato": dish.id if dish else "", "plato2": second.id if second else "",
        "dia": day, "titular": headline, "titulo": title, "oferta": offer,
        "precio": price_value or "", "formato": "historia" if story else "cuadrado",
    }
    return {
        "kind": kind, "dish": dish, "second": second, "day": day, "headline": headline, "title": title,
        "offer": offer, "price": clp(price_value) if price_value else "",
        "old_price": clp(old_price_value) if old_price_value else "",
        "venue": venue, "story": story, "query": {k: v for k, v in query.items() if v != ""},
    }


@login_required
def promo_generator(request):
    venues, dishes = _dishes_for(request)
    promo = resolve_promo(request.GET, venues, dishes)
    image_url = reverse("core:promo_image") + "?" + urlencode(promo["query"])
    return render(request, "core/promo_generator.html", {
        "promo": promo,
        "dishes": dishes,
        "types": PROMO_TYPES,
        "weekdays": list(enumerate(w.capitalize() for w in WEEKDAYS)),
        "image_url": image_url,
        "download_url": image_url + "&descargar=1",
        "caption": build_caption(promo["headline"], promo["title"], promo["offer"], promo["price"],
                                 promo["venue"].name if promo["venue"] else ""),
    })


@login_required
def promo_image(request):
    venues, dishes = _dishes_for(request)
    promo = resolve_promo(request.GET, venues, dishes)
    dish = promo["dish"]
    data = render_promo(
        headline=promo["headline"], title=promo["title"], offer=promo["offer"],
        price=promo["price"], old_price=promo["old_price"],
        venue_name=promo["venue"].name if promo["venue"] else "",
        image_path=dish.image.path if dish and dish.image else None, story=promo["story"],
    )
    response = HttpResponse(data, content_type="image/jpeg")
    if request.GET.get("descargar"):
        response["Content-Disposition"] = f'attachment; filename="promo_{promo["kind"]}.jpg"'
        if promo["venue"]:
            log_action(
                request, action=AuditLog.Action.EXPORT, module="marketing", venue=promo["venue"],
                object_type="PromoImage", object_id=promo["kind"],
                description=f"Descargó una pieza promocional: {promo['headline']} - {promo['title']}.",
            )
    return response
