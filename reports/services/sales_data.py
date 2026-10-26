from decimal import Decimal

from django.db.models import Avg, Count, Sum
from django.db.models.functions import ExtractHour, TruncDate

from sales.models import Order, OrderItem


def get_sales_data(venue, start_datetime, end_datetime):
    """Indicadores de ventas de un local entre dos fechas (fin exclusivo)."""
    orders = Order.objects.filter(service_session__table__venue=venue)

    paid = orders.filter(
        status=Order.Status.PAID,
        paid_at__gte=start_datetime,
        paid_at__lt=end_datetime,
    )
    cancelled = orders.filter(
        status=Order.Status.CANCELLED,
        cancelled_at__gte=start_datetime,
        cancelled_at__lt=end_datetime,
    )

    summary = paid.aggregate(
        orders_count=Count("id"),
        revenue=Sum("total"),
        average_ticket=Avg("total"),
        discounts=Sum("discount_amount"),
    )
    summary["revenue"] = summary["revenue"] or Decimal("0")
    summary["average_ticket"] = summary["average_ticket"] or Decimal("0")
    summary["discounts"] = summary["discounts"] or Decimal("0")
    summary["cancelled_count"] = cancelled.count()

    method_labels = dict(Order.PaymentMethod.choices)
    by_payment = [
        {
            "method": method_labels.get(row["payment_method"], row["payment_method"]),
            "orders_count": row["orders_count"],
            "revenue": row["revenue"],
        }
        for row in paid.values("payment_method")
        .annotate(orders_count=Count("id"), revenue=Sum("total"))
        .order_by("-revenue")
    ]

    top_dishes = list(
        OrderItem.objects.filter(order__in=paid)
        .values("dish_name")
        .annotate(units=Sum("quantity"), revenue=Sum("line_total"))
        .order_by("-units", "dish_name")[:5]
    )

    daily = list(
        paid.annotate(day=TruncDate("paid_at"))
        .values("day")
        .annotate(orders_count=Count("id"), revenue=Sum("total"))
        .order_by("day")
    )

    hourly = list(
        paid.annotate(hour=ExtractHour("paid_at"))
        .values("hour")
        .annotate(orders_count=Count("id"), revenue=Sum("total"))
        .order_by("hour")
    )

    return {
        "sales_summary": summary,
        "sales_by_payment": by_payment,
        "sales_top_dishes": top_dishes,
        "sales_daily": daily,
        "sales_hourly": hourly,
        "sales_chart_labels": [row["day"].strftime("%d-%m") for row in daily],
        "sales_chart_values": [float(row["revenue"]) for row in daily],
        "sales_hourly_labels": [f"{row['hour']:02d}:00" for row in hourly],
        "sales_hourly_values": [float(row["revenue"]) for row in hourly],
    }
