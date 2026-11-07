import csv
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from analytics.views import get_accessible_venues
from authentication.permissions import get_or_create_profile
from sales.models import Order


def _date(value, default):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default


@login_required
def sales_explorer(request):
    venues = get_accessible_venues(get_or_create_profile(request.user))
    params = request.GET
    today = timezone.localdate()
    start, end = _date(params.get("desde"), today - timedelta(days=6)), _date(params.get("hasta"), today)
    orders = (Order.objects.filter(service_session__table__venue__in=venues,
                                   opened_at__date__gte=start, opened_at__date__lte=end)
              .select_related("service_session__table__venue", "created_by").prefetch_related("items").order_by("-opened_at"))
    if params.get("local"):
        orders = orders.filter(service_session__table__venue_id=params["local"])
    if params.get("mesa"):
        orders = orders.filter(service_session__table__code__iexact=params["mesa"].strip())
    if params.get("estado"):
        orders = orders.filter(status=params["estado"])
    if params.get("pago"):
        orders = orders.filter(payment_method=params["pago"])
    if params.get("plato"):
        orders = orders.filter(items__dish_name__icontains=params["plato"].strip()).distinct()
    if params.get("registrado"):
        orders = orders.filter(created_by_id=params["registrado"])

    paid = orders.filter(status=Order.Status.PAID)
    totals = paid.aggregate(count=Count("id"), revenue=Sum("total"), ticket=Avg("total"), discounts=Sum("discount_amount"))

    if params.get("formato") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="ventas_{start:%Y%m%d}_{end:%Y%m%d}.csv"'
        response.write("\ufeff")
        writer = csv.writer(response, delimiter=";")
        writer.writerow(["Pedido", "Apertura", "Pago", "Local", "Mesa", "Estado", "Medio de pago", "Descuento", "Total", "Registrado por", "Platos"])
        for order in orders[:20000]:
            writer.writerow([order.id, timezone.localtime(order.opened_at).strftime("%d-%m-%Y %H:%M") if order.opened_at else "",
                             timezone.localtime(order.paid_at).strftime("%d-%m-%Y %H:%M") if order.paid_at else "",
                             order.service_session.table.venue.name, order.service_session.table.code,
                             order.get_status_display(), order.get_payment_method_display() if order.payment_method else "",
                             int(order.discount_amount or 0), int(order.total or 0),
                             order.created_by.username if order.created_by_id else "",
                             ", ".join(f"{i.quantity}× {i.dish_name}" for i in order.items.all())])
        return response

    query = params.copy()
    query.pop("page", None)
    payment_field = Order._meta.get_field("payment_method")
    return render(request, "reports/sales_explorer.html", {
        "page": Paginator(orders, 25).get_page(params.get("page")), "totals": totals, "matched": orders.count(),
        "start": start, "end": end, "f": params, "querystring": query.urlencode(), "venues": venues,
        "statuses": Order.Status.choices, "payments": [c for c in payment_field.choices if c[0]],
        "staff": User.objects.filter(pk__in=Order.objects.filter(service_session__table__venue__in=venues)
                                     .values("created_by_id")).order_by("username"),
    })
