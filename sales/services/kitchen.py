"""Pantallas de comandas (KDS) de cocina y barra, y aceptación agregada por plato o bebida."""
from collections import OrderedDict, defaultdict
from datetime import timedelta
from statistics import mean

from django.db.models import Avg, Count
from django.utils import timezone

from ai_vision.models import DetectionEvent
from operations.models import SatisfactionEvaluation, ServiceSession
from sales.models import Order, OrderItem

KITCHEN, BAR = "cocina", "barra"
STATIONS = {
    KITCHEN: {"title": "Cocina", "icon": "👨‍🍳", "warn": 10, "late": 20, "noun": "platos"},
    BAR: {"title": "Barra", "icon": "🍹", "warn": 5, "late": 10, "noun": "bebidas"},
}
BAR_WORDS = ("bebid", "trago", "coctel", "cóctel", "jugo", "cafe", "café", "cerveza", "vino", "drink")
FLOW = {"pending": "preparing", "preparing": "ready", "ready": "delivered"}
COLUMNS = [("pending", "Pendientes"), ("preparing", "En preparación"), ("ready", "Listos para servir")]
NEXT_LABEL = {"pending": "Comenzar", "preparing": "Listo", "ready": "Entregado"}
WINDOW = timedelta(minutes=15)


def station_for(item):
    """Barra para la categoría Bebida (o similares); el resto va a cocina."""
    category = (item.dish.category if item.dish_id and item.dish else "") or ""
    text = (category or item.dish_name or "").lower()
    return BAR if any(word in text for word in BAR_WORDS) else KITCHEN


def _minutes(start, end):
    return max(0, round((end - start).total_seconds() / 60)) if start and end else 0


def _since(item):
    order = item.order
    return order.confirmed_at or order.opened_at or item.created_at


def queue(venues, station, now=None):
    now = now or timezone.now()
    config = STATIONS[station]
    items = (OrderItem.objects
             .filter(order__service_session__table__venue__in=venues,
                     order__service_session__status=ServiceSession.Status.OPEN,
                     order__status__in=[Order.Status.CONFIRMED, Order.Status.PAID])
             .exclude(prep_status="delivered")
             .select_related("order__service_session__table", "dish"))
    groups = OrderedDict()
    for item in items:
        if station_for(item) != station:
            continue
        key = (item.prep_status, item.order_id)
        card = groups.setdefault(key, {"order": item.order, "table": item.order.service_session.table,
                                       "status": item.prep_status, "since": _since(item), "items": [], "ids": []})
        card["items"].append(item)
        card["ids"].append(item.id)

    columns = []
    for status, title in COLUMNS:
        cards = sorted((c for (s, _), c in groups.items() if s == status), key=lambda c: c["since"] or now)
        for card in cards:
            card["minutes"] = _minutes(card["since"], now)
            card["level"] = "late" if card["minutes"] >= config["late"] else "warn" if card["minutes"] >= config["warn"] else "ok"
            card["ids_csv"] = ",".join(str(i) for i in card["ids"])
            card["next_label"] = NEXT_LABEL[status]
        columns.append({"status": status, "title": title, "cards": cards})
    return {"station": station, "config": config, "columns": columns}


def advance(item_ids, venues, station=None):
    """Avanza cada ítem al siguiente estado. Usa update() para no alterar los totales del pedido."""
    now = timezone.now()
    changed = 0
    for item in OrderItem.objects.filter(pk__in=item_ids, order__service_session__table__venue__in=venues).select_related("dish"):
        if station and station_for(item) != station:
            continue
        nxt = FLOW.get(item.prep_status)
        if not nxt:
            continue
        changes = {"prep_status": nxt}
        if nxt == "preparing":
            changes["prep_started_at"] = now
        elif nxt == "ready":
            changes["ready_at"] = now
            if not item.prep_started_at:
                changes["prep_started_at"] = now
        elif nxt == "delivered":
            changes["delivered_at"] = now
        changed += OrderItem.objects.filter(pk=item.pk).update(**changes)
    return changed


def deliver_ready(session):
    return OrderItem.objects.filter(order__service_session=session, prep_status="ready").update(
        prep_status="delivered", delivered_at=timezone.now())


def ready_counts(sessions):
    counts = defaultdict(int)
    for session_id in OrderItem.objects.filter(order__service_session__in=sessions, prep_status="ready") \
            .values_list("order__service_session_id", flat=True):
        counts[session_id] += 1
    return counts


def acceptance(venues, station, days=7, now=None):
    """Por plato o bebida: unidades, preparación media, valoración e IBE de las mesas que lo recibieron."""
    now = now or timezone.now()
    since = now - timedelta(days=days)
    items = [item for item in OrderItem.objects
             .filter(order__service_session__table__venue__in=venues, order__opened_at__gte=since)
             .exclude(order__status=Order.Status.CANCELLED)
             .select_related("order", "dish")
             if station_for(item) == station]
    if not items:
        return []

    sessions = {item.order.service_session_id for item in items}
    events = defaultdict(list)
    for session_id, moment, valence in (DetectionEvent.objects
                                        .filter(service_session_id__in=sessions, valence__isnull=False)
                                        .values_list("service_session_id", "detected_at", "valence")):
        events[session_id].append((moment, float(valence)))

    rows = defaultdict(lambda: {"units": 0, "prep": [], "after": [], "delta": []})
    for item in items:
        key = (item.dish_id, item.dish_name)
        row = rows[key]
        row["units"] += item.quantity
        start = item.prep_started_at or item.order.confirmed_at
        if item.ready_at and start:
            row["prep"].append((item.ready_at - start).total_seconds() / 60)
        moment = item.delivered_at or item.ready_at or item.order.confirmed_at or item.order.opened_at
        if not moment:
            continue
        session_events = events.get(item.order.service_session_id, [])
        before = [v for t, v in session_events if moment - WINDOW <= t < moment]
        after = [v for t, v in session_events if moment <= t <= moment + WINDOW]
        if after:
            row["after"].append(mean(after))
            if before:
                row["delta"].append(mean(after) - mean(before))

    ratings = {r["dish_id"]: r for r in SatisfactionEvaluation.objects
               .filter(dish_id__in=[k[0] for k in rows if k[0]], service_session__started_at__gte=since)
               .values("dish_id").annotate(avg=Avg("rating"), n=Count("id"))}
    result = []
    for (dish_id, name), row in rows.items():
        rating = ratings.get(dish_id)
        result.append({
            "name": name, "units": row["units"],
            "prep_min": mean(row["prep"]) if row["prep"] else None,
            "csat": float(rating["avg"]) if rating else None, "csat_n": rating["n"] if rating else 0,
            "ibe_after": mean(row["after"]) if row["after"] else None,
            "ibe_delta": mean(row["delta"]) if row["delta"] else None, "ibe_n": len(row["delta"]),
        })
    return sorted(result, key=lambda r: -r["units"])[:10]
