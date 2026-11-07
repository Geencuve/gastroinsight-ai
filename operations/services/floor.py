"""Estado de la sala: mesas por estado, lista de espera y termómetro de experiencia por mesa."""
from collections import defaultdict

from django.db.models import Avg, Max
from django.utils import timezone

from ai_vision.models import DetectionEvent
from ai_vision.services.live import build_live_state
from operations.models import RestaurantTable, ServiceSession, WaitlistEntry
from sales.models import Order

STATES = {
    "libre": ("Libre", "free"),
    "esperando_pedido": ("Esperando pedido", "waiting"),
    "consumiendo": ("Consumiendo", "eating"),
    "cuenta": ("Cuenta solicitada", "bill"),
    "por_cerrar": ("Pagada · por cerrar", "paid"),
}
PENDING = (Order.Status.OPEN, Order.Status.CONFIRMED)


def minutes_between(start, end):
    if not start or not end:
        return None
    return max(0, round((end - start).total_seconds() / 60))


def session_state(session, orders):
    active = [o for o in orders if o.status != Order.Status.CANCELLED]
    pending = [o for o in active if o.status in PENDING]
    if session.bill_requested_at and pending:
        return "cuenta"
    if active and not pending:
        return "por_cerrar"
    if any(o.status in (Order.Status.CONFIRMED, Order.Status.PAID) for o in active):
        return "consumiendo"
    return "esperando_pedido"


def build_floor(venues):
    now = timezone.now()
    tables = list(RestaurantTable.objects.filter(venue__in=venues, is_active=True)
                  .select_related("venue").order_by("zone_name", "code"))
    sessions = {s.table_id: s for s in ServiceSession.objects.filter(table__in=tables, status=ServiceSession.Status.OPEN)}
    orders = defaultdict(list)
    for order in Order.objects.filter(service_session__in=list(sessions.values())):
        orders[order.service_session_id].append(order)
    live = {card["table"]: card for card in build_live_state(venues)["cards"]}
    from sales.services.kitchen import ready_counts

    ready = ready_counts(list(sessions.values()))

    zones, counts = defaultdict(list), {key: 0 for key in STATES}
    for table in tables:
        session = sessions.get(table.id)
        card = {"table": table, "session": session, "live": live.get(table.code), "alerts": []}
        if session is None:
            state = "libre"
        else:
            session_orders = orders[session.id]
            state = session_state(session, session_orders)
            active = [o for o in session_orders if o.status != Order.Status.CANCELLED]
            pending = [o for o in active if o.status in PENDING]
            first = min((o.opened_at for o in active if o.opened_at), default=None)
            card.update({
                "guests": session.guests_count,
                "seated_min": minutes_between(session.started_at, now),
                "first_order_min": minutes_between(session.started_at, first),
                "arrival_wait_min": minutes_between(session.arrived_at, session.started_at),
                "bill_min": minutes_between(session.bill_requested_at, now),
                "pending_count": len(pending),
                "pending_total": sum((o.total or 0) for o in pending),
                "ready_count": ready[session.id],
            })
            if state == "esperando_pedido" and card["seated_min"] >= 10:
                card["alerts"].append(f"Esperando pedido hace {card['seated_min']} min")
            if state == "cuenta" and (card["bill_min"] or 0) >= 8:
                card["alerts"].append(f"Pidió la cuenta hace {card['bill_min']} min")
            if state == "por_cerrar":
                card["alerts"].append("Pagada: cerrar la mesa")
            if card["ready_count"]:
                card["alerts"].insert(0, f"{card['ready_count']} plato(s) listos para servir")
            if card["live"]:
                card["alerts"] += [r for r in card["live"]["reasons"] if not r.startswith("Sin atención")]
        label, css = STATES[state]
        card.update({"state": state, "state_label": label, "css": css})
        counts[state] += 1
        zones[table.zone_name or "Salón"].append(card)

    return {
        "zones": sorted(zones.items()),
        "counts": [(STATES[key][0], STATES[key][1], value) for key, value in counts.items()],
        "waitlist": list(WaitlistEntry.objects.filter(venue__in=venues, seated_at__isnull=True, cancelled=False)),
        "free_tables": [t for t in tables if t.id not in sessions],
    }


SUGGESTIONS = {
    "rojo": "Ofrece un detalle de cortesía (por ejemplo, un café) y pregunta con amabilidad cómo estuvo la atención.",
    "amarillo": "Agradece la paciencia y pregunta si todo estuvo bien antes de cobrar.",
    "verde": "Experiencia sin incidencias: agradece la visita e invita a dejar su opinión con el código QR.",
}
LABELS = {"rojo": "Experiencia en riesgo", "amarillo": "Atención", "verde": "Experiencia positiva"}


def thermometer(session, now=None):
    """Termómetro de la mesa (no de una persona): métricas agregadas y tiempos de la atención."""
    now = now or timezone.now()
    orders = list(Order.objects.filter(service_session=session).exclude(status=Order.Status.CANCELLED))
    visual = DetectionEvent.objects.filter(service_session=session).aggregate(
        ieo=Avg("experience_index"), attention=Max("attention_seeking"))
    ieo = float(visual["ieo"]) if visual["ieo"] is not None else None
    first = min((o.opened_at for o in orders if o.opened_at), default=None)

    red, yellow = [], []
    if ieo is not None and ieo < 45:
        red.append(f"Experiencia observable baja durante la visita (IEO {ieo:.0f})")
    elif ieo is not None and ieo < 60:
        yellow.append(f"Experiencia observable regular (IEO {ieo:.0f})")
    if visual["attention"] is not None and float(visual["attention"]) >= 0.30:
        yellow.append("Buscaron atención durante la visita")
    first_wait = minutes_between(session.started_at, first)
    if first_wait is not None and first_wait >= 15:
        yellow.append(f"Esperaron {first_wait} min el primer pedido")
    seat_wait = minutes_between(session.arrived_at, session.started_at)
    if seat_wait is not None and seat_wait >= 15:
        yellow.append(f"Esperaron {seat_wait} min por una mesa")
    bill_wait = minutes_between(session.bill_requested_at, now)
    if bill_wait is not None and bill_wait >= 10:
        yellow.append(f"Esperan la cuenta hace {bill_wait} min")

    level = "rojo" if red or len(yellow) >= 2 else ("amarillo" if yellow else "verde")
    return {"level": level, "label": LABELS[level], "reasons": red + yellow, "suggestion": SUGGESTIONS[level],
            "ieo": ieo, "has_visual": ieo is not None}
