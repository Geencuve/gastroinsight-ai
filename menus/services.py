from datetime import timedelta

from django.db.models import Avg, Count, Sum
from django.utils import timezone

from operations.models import SatisfactionEvaluation
from sales.models import Order, OrderItem

CATEGORY_ORDER = ["Entrada", "Fondo", "Postre", "Bebida"]


def sort_dishes(dishes):
    def key(dish):
        category = dish.category or "Otros"
        position = CATEGORY_ORDER.index(category) if category in CATEGORY_ORDER else len(CATEGORY_ORDER)
        return (position, category, dish.name)
    return sorted(dishes, key=key)


def categories_of(dishes):
    found = {dish.category or "Otros" for dish in dishes}
    ordered = [c for c in CATEGORY_ORDER if c in found]
    return ordered + sorted(found - set(ordered))


def build_dish_cards(dishes):
    """Tarjetas de platos con valoración promedio y ventas de las últimas 4 semanas."""
    dishes = sort_dishes(dishes)
    ids = [dish.id for dish in dishes]
    ratings = {
        row["dish_id"]: row
        for row in SatisfactionEvaluation.objects.filter(dish_id__in=ids)
        .values("dish_id").annotate(avg=Avg("rating"), count=Count("id"))
    }
    since = timezone.now() - timedelta(days=28)
    units = dict(
        OrderItem.objects.filter(
            dish_id__in=ids, order__status=Order.Status.PAID, order__paid_at__gte=since,
        ).values("dish_id").annotate(total=Sum("quantity")).values_list("dish_id", "total")
    )
    top = set(sorted(units, key=units.get, reverse=True)[:3])
    return [
        {
            "dish": dish,
            "rating": ratings.get(dish.id, {}).get("avg"),
            "rating_count": ratings.get(dish.id, {}).get("count", 0),
            "units": units.get(dish.id, 0),
            "is_top": dish.id in top and units.get(dish.id, 0) > 0,
        }
        for dish in dishes
    ]
