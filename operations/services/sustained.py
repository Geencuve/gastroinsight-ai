"""
Alertas por umbral sostenido (J2). Una condición solo dispara una alerta si se mantiene durante el tiempo
configurado: al menos el 80% de las lecturas del período la cumplen y los datos cubren el período completo (con 1 minuto de tolerancia).
Índice de impaciencia (0-100) = 60% búsqueda de atención + 40% (100 − IEO). Siempre por mesa, nunca por persona.
"""
from datetime import timedelta

from django.utils import timezone

SHARE = 0.8
COVERAGE_TOLERANCE = 60  # segundos


def alert_settings(venue):
    from operations.models import AlertSettings

    return AlertSettings.objects.filter(venue=venue).first() or AlertSettings(venue=venue)


def impatience(attention, ieo):
    if attention is None and ieo is None:
        return None
    parts, weights = [], []
    if attention is not None:
        parts.append(float(attention) * 100 * 0.6)
        weights.append(0.6)
    if ieo is not None:
        parts.append((100 - float(ieo)) * 0.4)
        weights.append(0.4)
    return round(sum(parts) / sum(weights), 1)


def _window(table, minutes):
    from ai_vision.models import DetectionEvent

    now = timezone.now()
    events = list(DetectionEvent.objects.filter(table=table, detected_at__gte=now - timedelta(minutes=minutes))
                  .order_by("detected_at").values_list("detected_at", "attention_seeking", "experience_index"))
    # Los datos deben cubrir el período completo (tolerancia de 1 minuto entre lecturas)
    if len(events) < 3 or (now - events[0][0]).total_seconds() < minutes * 60 - COVERAGE_TOLERANCE:
        return None
    return events


def sustained_impatience(table, settings):
    """Devuelve (promedio, minutos) si la impaciencia supera el umbral de forma sostenida; si no, None."""
    if not table or not settings.impatience_minutes:
        return None
    events = _window(table, settings.impatience_minutes)
    if not events:
        return None
    values = [v for v in (impatience(att, ieo) for _, att, ieo in events) if v is not None]
    if not values or sum(v >= settings.impatience_pct for v in values) / len(values) < SHARE:
        return None
    return round(sum(values) / len(values)), settings.impatience_minutes


def sustained_low_ieo(table, settings):
    """True si el IEO se mantiene bajo el umbral el tiempo configurado (o de inmediato si son 0 minutos)."""
    if not settings.discomfort_minutes:
        return True
    events = _window(table, settings.discomfort_minutes) if table else None
    if not events:
        return False
    values = [float(ieo) for _, _, ieo in events if ieo is not None]
    return bool(values) and sum(v < settings.discomfort_ieo for v in values) / len(values) >= SHARE
