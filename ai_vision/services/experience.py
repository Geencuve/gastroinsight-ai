"""
Índice de Experiencia Observable (IEO), 0 a 100.

Indicador EXPLORATORIO que combina señales agregadas y anónimas:
  - 60% valencia de las expresiones (-1 a 1, llevada a 0-100)
  - 25% búsqueda de atención invertida (rostros girados mirando alrededor)
  - 15% tiempo sin atención en la mesa (minutos desde la última actividad de pedido)

No mide la satisfacción directamente: se valida contra la valoración voluntaria
(CSAT) en el panel de correlación.
"""
from django.db.models import Max

WEIGHTS = {"valence": 0.60, "attention": 0.25, "wait": 0.15}
VALENCE_BY_EMOTION = {
    "neutral": 0.0, "happy": 1.0, "surprised": 0.3, "sad": -0.8,
    "angry": -1.0, "disgust": -0.9, "fear": -0.7, "contempt": -0.8,
}


def valence_from_distribution(distribution):
    total = sum((distribution or {}).values())
    if not total:
        return None
    return sum(VALENCE_BY_EMOTION.get(k, 0.0) * v for k, v in distribution.items()) / total


def experience_index(valence, attention_seeking, wait_minutes=None):
    parts = []
    if valence is not None:
        parts.append((WEIGHTS["valence"], (max(-1.0, min(1.0, valence)) + 1) / 2 * 100))
    if attention_seeking is not None:
        parts.append((WEIGHTS["attention"], (1 - min(1.0, attention_seeking * 2)) * 100))
    if wait_minutes is not None:
        parts.append((WEIGHTS["wait"], max(0.0, 100 - max(0.0, wait_minutes - 10) * 4)))
    if not parts or (valence is None and attention_seeking is None):
        return None
    return round(sum(w * v for w, v in parts) / sum(w for w, _ in parts), 2)


def wait_minutes(service_session, moment):
    """Minutos desde la última actividad de pedido en la mesa (o desde que se sentaron)."""
    if service_session is None:
        return None
    from sales.models import Order, OrderItem

    last = service_session.started_at
    item = OrderItem.objects.filter(order__service_session=service_session).aggregate(last=Max("created_at"))["last"]
    order = Order.objects.filter(service_session=service_session).aggregate(
        opened=Max("opened_at"), confirmed=Max("confirmed_at"), paid=Max("paid_at"),
    )
    for value in (item, order["opened"], order["confirmed"], order["paid"]):
        if value and value > last and value <= moment:
            last = value
    return max(0.0, (moment - last).total_seconds() / 60)
