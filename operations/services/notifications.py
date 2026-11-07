"""
Motor de alertas del local. Revisa el estado en vivo y crea notificaciones sin duplicarlas.
Todo es por mesa (métricas agregadas): nunca identifica ni sigue a una persona.
"""
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from authentication.roles import (BAR, CASHIER, KITCHEN, MANAGERS, OPERATOR, SUPERVISOR, VIEWER, WAITER, role_key)
from operations.models import Notification, RestaurantTable, WaitlistEntry

ACTIVE_MINUTES = 15
ICONS = {"attention": "🙋", "discomfort": "😟", "approval": "😊", "arrival": "🚶", "waiting": "⏱️", "ready": "🍽️", "bill": "🧾"}
PRIORITY = {"danger": 0, "warning": 1, "info": 2, "success": 3}
SERVICE_KINDS = {"attention", "discomfort", "arrival", "waiting", "ready", "bill"}
KIND_ROLES = {
    WAITER: SERVICE_KINDS,
    CASHIER: {"bill"},
    KITCHEN: set(), BAR: set(), VIEWER: set(),
    SUPERVISOR: SERVICE_KINDS | {"approval"},
    OPERATOR: SERVICE_KINDS | {"approval"},
}


def kinds_for(profile):
    key = role_key(profile)
    if key in MANAGERS:
        return SERVICE_KINDS | {"approval"}
    return KIND_ROLES.get(key, set())


def _notify(venue, table, kind, level, title, message, key, window_minutes=10):
    since = timezone.now() - timedelta(minutes=window_minutes)
    if Notification.objects.filter(venue=venue, dedupe_key=key, created_at__gte=since).exists():
        return None
    return Notification.objects.create(venue=venue, table=table, kind=kind, level=level, title=title[:120],
                                       message=message[:255], dedupe_key=key[:120])


def _from_live(venue, tables):
    from ai_vision.services.live import build_live_state

    for card in build_live_state([venue])["cards"]:
        table = tables.get(card["table"])
        code = card["table"]
        if not card["live"]:
            continue
        if card["attention_pct"] is not None and card["attention_pct"] >= 30:
            _notify(venue, table, "attention", "danger", f"Mesa {code} busca atención",
                    f"El {card['attention_pct']}% de los rostros mira alrededor.", f"attention:{code}")
        if card["ieo"] is not None and card["ieo"] < 45:
            _notify(venue, table, "discomfort", "danger", f"Mesa {code}: posible disconformidad",
                    f"Experiencia observable baja (IEO {card['ieo']:.0f}). Acércate a preguntar cómo va todo.",
                    f"discomfort:{code}")
        elif card["ieo_trend"] is not None and card["ieo_trend"] <= -10:
            _notify(venue, table, "discomfort", "warning", f"Mesa {code}: la experiencia va a la baja",
                    f"El IEO bajó {abs(card['ieo_trend']):.0f} puntos en los últimos minutos.", f"trend:{code}")
        elif card["ieo"] is not None and card["ieo"] >= 80:
            _notify(venue, table, "approval", "success", f"Mesa {code}: señales de aprobación",
                    f"Experiencia observable alta (IEO {card['ieo']:.0f}). Buen momento para ofrecer postre o café.",
                    f"approval:{code}", window_minutes=20)
        if card["wait_min"] is not None and card["wait_min"] >= 20:
            _notify(venue, table, "waiting", "warning", f"Mesa {code} sin atención hace {card['wait_min']} min",
                    "No hay actividad de pedidos reciente.", f"waiting:{code}")
        if not card["has_session"] and (card["occupancy"] or 0) >= 1:
            _notify(venue, table, "arrival", "info", f"Clientes en la mesa {code}",
                    "Hay personas sentadas y la mesa no tiene atención abierta.", f"seated:{code}")


def _from_floor(venue):
    from operations.services.floor import build_floor

    for _, cards in build_floor([venue])["zones"]:
        for card in cards:
            session = card["session"]
            if session is None:
                continue
            code = card["table"].code
            if card.get("ready_count"):
                _notify(venue, card["table"], "ready", "info", f"Mesa {code}: {card['ready_count']} plato(s) listos",
                        "Retíralos de cocina o barra y llévalos a la mesa.", f"ready:{session.id}:{card['ready_count']}", 60)
            if session.bill_requested_at:
                _notify(venue, card["table"], "bill", "info", f"Mesa {code} pidió la cuenta",
                        "Lleva la cuenta o avisa a caja.", f"bill:{session.id}:{session.bill_requested_at:%H%M%S}", 240)


def _arrivals(venue):
    from ai_vision.models import DetectionEvent
    from cameras.models import Camera

    for entry in WaitlistEntry.objects.filter(venue=venue, cancelled=False, seated_at__isnull=True,
                                              arrived_at__gte=timezone.now() - timedelta(minutes=5)):
        _notify(venue, None, "arrival", "info", f"Llegó un grupo de {entry.guests}",
                f"{entry.party_name or 'Grupo'} espera mesa.", f"waitlist:{entry.id}", 60)
    for camera in Camera.objects.filter(venue=venue, is_active=True, is_entrance=True):
        recent = list(DetectionEvent.objects.filter(session__camera=camera,
                                                    detected_at__gte=timezone.now() - timedelta(minutes=2))
                      .order_by("-detected_at")[:2])
        if len(recent) == 2:
            count = lambda e: float(e.persons_detected if e.persons_detected is not None else (e.occupancy or 0))
            new = round(count(recent[0]) - count(recent[1]))
            if new >= 1:
                _notify(venue, None, "arrival", "info", f"Ingresan {new} persona(s)",
                        f"Detectado por {camera.name}.", f"entrance:{camera.id}:{recent[0].id}", 60)


def generate(venues):
    """Crea las alertas nuevas (como máximo una vez cada 5 segundos por conjunto de locales)."""
    venue_ids = sorted(v.id for v in venues)
    if not venue_ids or not cache.add(f"gi-alerts-{'-'.join(map(str, venue_ids))}", 1, timeout=5):
        return
    for venue in venues:
        tables = {t.code: t for t in RestaurantTable.objects.filter(venue=venue)}
        _from_live(venue, tables)
        _from_floor(venue)
        _arrivals(venue)


def active_for(profile, venues, limit=20):
    kinds = kinds_for(profile)
    if not kinds:
        return []
    since = timezone.now() - timedelta(minutes=ACTIVE_MINUTES)
    items = list(Notification.objects.filter(venue__in=venues, kind__in=kinds, acknowledged_at__isnull=True,
                                             created_at__gte=since).select_related("table")[:limit])
    return sorted(items, key=lambda n: (PRIORITY.get(n.level, 9), -n.created_at.timestamp()))


def serialize(notification):
    from django.urls import reverse

    minutes = max(0, round((timezone.now() - notification.created_at).total_seconds() / 60))
    return {"id": notification.id, "kind": notification.kind, "level": notification.level,
            "icon": ICONS.get(notification.kind, "🔔"), "title": notification.title, "message": notification.message,
            "table": notification.table.code if notification.table_id else "", "minutes": minutes,
            "ack_url": reverse("alerts:ack", args=[notification.id])}
