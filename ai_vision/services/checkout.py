"""Lectura de la cámara de caja: experiencia observable agregada frente a la caja (nunca por persona)."""
from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone


def checkout_reading(venues, start, end):
    from ai_vision.models import DetectionEvent

    stats = DetectionEvent.objects.filter(
        session__camera__venue__in=venues, session__camera__is_checkout=True,
        detected_at__gte=start, detected_at__lte=end,
    ).aggregate(n=Count("id"), ieo=Avg("experience_index"), ibe=Avg("valence"), att=Avg("attention_seeking"),
                faces=Avg("faces_count"))
    if not stats["n"]:
        return None
    ieo = float(stats["ieo"]) if stats["ieo"] is not None else None
    return {
        "readings": stats["n"], "ieo": round(ieo) if ieo is not None else None,
        "ibe": round(float(stats["ibe"]), 2) if stats["ibe"] is not None else None,
        "attention_pct": round(float(stats["att"]) * 100) if stats["att"] is not None else None,
        "faces": round(float(stats["faces"] or 0), 1),
        "level": None if ieo is None else ("verde" if ieo >= 65 else "amarillo" if ieo >= 45 else "rojo"),
    }


def live_checkout(venues, seconds=60):
    now = timezone.now()
    return checkout_reading(venues, now - timedelta(seconds=seconds), now)


def checkout_at_payment(order):
    if not order.paid_at:
        return None
    venue = order.service_session.table.venue
    return checkout_reading([venue], order.paid_at - timedelta(seconds=90), order.paid_at + timedelta(seconds=15))
