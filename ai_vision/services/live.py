"""Estado en tiempo real de las mesas: IEO, señales visuales agregadas y operación."""
from collections import defaultdict
from datetime import timedelta
from statistics import mean

from django.db.models import Count, Sum
from django.utils import timezone

from ai_vision.models import DetectionEvent
from ai_vision.services.experience import wait_minutes
from cameras.models import Camera
from operations.models import RestaurantTable, ServiceSession
from sales.models import Order

LIVE_SECONDS = 120
LEVEL_ORDER = {"alerta": 0, "atencion": 1, "ok": 2}


def _avg(values):
    numbers = [float(v) for v in values if v is not None]
    return round(mean(numbers), 2) if numbers else None


def _clp(value):
    return "$" + f"{int(value or 0):,}".replace(",", ".")


def build_live_state(venues, window_minutes=5):
    now = timezone.now()
    tables = list(RestaurantTable.objects.filter(venue__in=venues, is_active=True).order_by("code"))
    cameras = {c.table_id: c for c in Camera.objects.filter(venue__in=venues, is_active=True, table__isnull=False)}
    sessions = {s.table_id: s for s in ServiceSession.objects.filter(table__in=tables, status=ServiceSession.Status.OPEN)}

    events = defaultdict(list)
    for event in DetectionEvent.objects.filter(
        table__in=tables, detected_at__gte=now - timedelta(minutes=window_minutes),
    ).order_by("detected_at").values(
        "table_id", "detected_at", "experience_index", "valence", "attention_seeking",
        "occupancy", "activity_level", "session__camera__source_type",
    ):
        events[event["table_id"]].append(event)

    pending = {
        row["service_session__table_id"]: row
        for row in Order.objects.filter(
            service_session__in=list(sessions.values()), status__in=[Order.Status.OPEN, Order.Status.CONFIRMED],
        ).values("service_session__table_id").annotate(count=Count("id"), total=Sum("total"))
    }

    cards, alerts = [], []
    for table in tables:
        session, camera, table_events = sessions.get(table.id), cameras.get(table.id), events.get(table.id, [])
        if session is None and camera is None:
            continue
        last = table_events[-1] if table_events else None
        seconds_since = int((now - last["detected_at"]).total_seconds()) if last else None
        live = seconds_since is not None and seconds_since <= LIVE_SECONDS
        recent = [e for e in table_events if (now - e["detected_at"]).total_seconds() <= 120]
        earlier = [e for e in table_events if (now - e["detected_at"]).total_seconds() > 120]
        ieo = _avg(e["experience_index"] for e in recent)
        previous = _avg(e["experience_index"] for e in earlier)
        attention = _avg(e["attention_seeking"] for e in recent)
        wait = wait_minutes(session, now) if session else None
        pend = pending.get(table.id)

        level, reasons = "ok", []
        if live and attention is not None and attention >= 0.30:
            level = "alerta"
            reasons.append("Clientes buscando atención")
        if live and ieo is not None and ieo < 45:
            level = "alerta"
            reasons.append("Experiencia observable baja")
        if live and ieo is not None and previous is not None and ieo - previous <= -10:
            level = "alerta" if level == "alerta" else "atencion"
            reasons.append("Índice en descenso")
        if wait is not None and wait >= 20:
            level = "alerta" if level == "alerta" else "atencion"
            reasons.append(f"Sin atención hace {wait:.0f} min")
        for reason in reasons:
            alerts.append({"table": table.code, "text": reason, "level": level})

        cards.append({
            "table": table.code,
            "zone": table.zone_name,
            "level": level,
            "reasons": reasons,
            "live": live,
            "has_camera": camera is not None,
            "has_session": session is not None,
            "synthetic": bool(last and last["session__camera__source_type"] == Camera.SourceType.DEMO),
            "seconds_since": seconds_since,
            "ieo": ieo,
            "ieo_trend": round(ieo - previous, 1) if ieo is not None and previous is not None else None,
            "valence": _avg(e["valence"] for e in recent),
            "attention_pct": round(attention * 100) if attention is not None else None,
            "occupancy": _avg(e["occupancy"] for e in recent),
            "activity": _avg(e["activity_level"] for e in recent),
            "seated_min": round((now - session.started_at).total_seconds() / 60) if session else None,
            "wait_min": round(wait) if wait is not None else None,
            "guests": session.guests_count if session else None,
            "pending_count": pend["count"] if pend else 0,
            "pending_total": _clp(pend["total"]) if pend else "$0",
            "spark": [float(e["experience_index"]) for e in table_events[-20:] if e["experience_index"] is not None],
        })

    cards.sort(key=lambda c: (LEVEL_ORDER[c["level"]], c["table"]))
    live_ieo = [c["ieo"] for c in cards if c["live"] and c["ieo"] is not None]
    return {
        "generated_at": timezone.localtime(now).strftime("%H:%M:%S"),
        "cards": cards,
        "alerts": alerts,
        "summary": {
            "tables": len(cards),
            "live_tables": sum(1 for c in cards if c["live"]),
            "average_ieo": round(mean(live_ieo), 1) if live_ieo else None,
            "alerts": len(alerts),
        },
    }
