"""
Experiencia por etapa del Customer Journey: IEO promedio en cada tramo de la atención.
Llegada y pedido → Esperando los platos → Comiendo → Cuenta y pago. Siempre por mesa, nunca por persona.
"""
from datetime import timedelta

from django.db.models import Min
from django.utils import timezone

STAGES = [
    ("llegada", "Llegada y pedido"),
    ("espera", "Esperando los platos"),
    ("consumo", "Comiendo"),
    ("cuenta", "Cuenta y pago"),
]
ACTIONS = {
    "llegada": "Acorta el tiempo hasta tomar el pedido: saluda, entrega la carta y ofrece bebida apenas se sienten.",
    "espera": "Revisa los tiempos de cocina en las horas punta y avisa a la mesa si un plato se demora.",
    "consumo": "Pasa por la mesa a los pocos minutos de servir y revisa presentación y temperatura de los platos.",
    "cuenta": "Lleva la cuenta apenas la pidan y agiliza el cobro: es la última impresión de la visita.",
}


def session_stages(session):
    from sales.models import Order, OrderItem

    orders = list(Order.objects.filter(service_session=session))
    confirmed = min((o.confirmed_at for o in orders if o.confirmed_at), default=None)
    delivered = OrderItem.objects.filter(order__service_session=session, delivered_at__isnull=False).aggregate(
        first=Min("delivered_at"))["first"]
    paid = max((o.paid_at for o in orders if o.paid_at), default=None)
    bill = getattr(session, "bill_requested_at", None)
    end = getattr(session, "ended_at", None) or getattr(session, "closed_at", None) or paid or timezone.now()
    bounds = [("llegada", session.started_at, confirmed or end), ("espera", confirmed, delivered),
              ("consumo", delivered, bill or paid or end), ("cuenta", bill, paid or end)]
    return [(key, start, stop) for key, start, stop in bounds if start and stop and stop > start]


def journey_stats(venues, days=14, limit=200):
    from ai_vision.models import DetectionEvent
    from operations.models import ServiceSession

    since = timezone.now() - timedelta(days=days)
    values = {key: [] for key, _ in STAGES}
    sessions = ServiceSession.objects.filter(table__venue__in=venues, started_at__gte=since).order_by("-started_at")[:limit]
    for session in sessions:
        events = list(DetectionEvent.objects.filter(service_session=session, experience_index__isnull=False)
                      .values_list("detected_at", "experience_index"))
        if not events:
            continue
        for key, start, stop in session_stages(session):
            readings = [float(ieo) for moment, ieo in events if start <= moment < stop]
            if readings:
                values[key].append(sum(readings) / len(readings))
    return [{"key": key, "label": label, "n": len(values[key]),
             "ieo": round(sum(values[key]) / len(values[key]), 1) if values[key] else None, "action": ACTIONS[key]}
            for key, label in STAGES]
