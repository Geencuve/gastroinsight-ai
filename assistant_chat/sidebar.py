from datetime import timedelta

from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from ai_vision.services.live import build_live_state
from analytics.views import get_accessible_venues
from authentication.permissions import get_or_create_profile
from core.services.insights import build_home_summary, build_insights
from sales.models import Order, OrderItem

TOOLS = [
    ("📡", "Monitor en vivo", "ai_vision:monitor", "IEO y alertas por mesa"),
    ("🎨", "Promociones", "core:promo_generator", "Piezas para redes en segundos"),
    ("📈", "Correlación", "analytics:correlation", "Tiempo, expresiones y CSAT"),
    ("⭐", "Opiniones por QR", "feedback:qr", "Calificaciones de clientes"),
    ("🍽️", "Carta y fotos", "menus:list", "Platos, fotos y ventas"),
    ("🧾", "Reportes", "reports:list", "PDF y CSV del período"),
]


def assistant_sidebar(user):
    venues = get_accessible_venues(get_or_create_profile(user))
    insights = build_insights(venues)
    top_dish = (
        OrderItem.objects.filter(
            order__service_session__table__venue__in=venues, order__status=Order.Status.PAID,
            order__paid_at__gte=timezone.now() - timedelta(days=28),
        ).values("dish_name").annotate(units=Sum("quantity")).order_by("-units").first()
    )
    return {
        "side_summary": build_home_summary(venues),
        "side_live": build_live_state(venues)["summary"],
        "side_ideas": (insights["ventas"] + insights["marketing"])[:2],
        "side_alerts": insights["now"][:3],
        "side_top_dish": top_dish["dish_name"] if top_dish else None,
        "side_tools": [{"icon": i, "label": l, "url": reverse(u), "hint": h} for i, l, u, h in TOOLS],
    }
