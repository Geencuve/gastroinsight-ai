"""
Journey del cliente: experiencia por etapa (IEO) del local y de cada atención, al estilo del
Customer Journey Map. Siempre agregado por mesa, nunca por persona.
"""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from analytics.views import get_accessible_venues
from authentication.permissions import get_or_create_profile

from .models import ServiceSession
from .services.journey import ACTIONS, STAGES, journey_stats, session_stages

LABELS = dict(STAGES)
PERIODS = (1, 7, 14, 30)


def emoji(value):
    if value is None:
        return "·"
    return "😄" if value >= 65 else "😐" if value >= 45 else "😟"


def _y(value):
    """IEO 0–100 → coordenada vertical del gráfico (250 abajo, 50 arriba)."""
    return round(250 - float(value) * 2.0, 1)


def _venues(request):
    return get_accessible_venues(get_or_create_profile(request.user))


def checkout_stage(venues, days):
    from ai_vision.services.checkout import checkout_at_payment
    from sales.models import Order

    paid = Order.objects.filter(service_session__table__venue__in=venues, status=Order.Status.PAID,
                                paid_at__gte=timezone.now() - timedelta(days=days)).select_related("service_session__table__venue")[:200]
    readings = [r["ieo"] for r in (checkout_at_payment(o) for o in paid) if r and r["ieo"] is not None]
    return {"key": "caja", "label": "Pago en caja", "n": len(readings),
            "ieo": round(sum(readings) / len(readings), 1) if readings else None,
            "action": "Agiliza el cobro y despide con amabilidad: es la última impresión de la visita."}


@login_required
def journey_overview(request):
    from ai_vision.models import DetectionEvent

    venues = _venues(request)
    try:
        days = int(request.GET.get("dias", 14))
    except ValueError:
        days = 14
    days = days if days in PERIODS else 14
    stages = journey_stats(venues, days) + [checkout_stage(venues, days)]
    step = 900 / len(stages)
    for index, stage in enumerate(stages):
        stage["x"] = round(step * index + step / 2, 1)
        stage["note_x"] = round(stage["x"] - 70, 1)
        stage["y"] = _y(stage["ieo"]) if stage["ieo"] is not None else None
        stage["ey"] = round(stage["y"] + 7, 1) if stage["y"] is not None else None
        stage["emoji"] = emoji(stage["ieo"])
    measured = [s for s in stages if s["ieo"] is not None]
    recent_ids = []
    for session_id in (DetectionEvent.objects.filter(service_session__table__venue__in=venues, service_session__isnull=False)
                       .order_by("-detected_at").values_list("service_session_id", flat=True)[:400]):
        if session_id not in recent_ids:
            recent_ids.append(session_id)
        if len(recent_ids) >= 12:
            break
    return render(request, "operations/journey.html", {
        "stages": stages, "days": days, "periods": PERIODS,
        "polyline": " ".join(f"{s['x']},{s['y']}" for s in stages if s["y"] is not None),
        "pain": min(measured, key=lambda s: s["ieo"]) if measured else None,
        "best": max(measured, key=lambda s: s["ieo"]) if measured else None,
        "sessions": ServiceSession.objects.filter(pk__in=recent_ids).select_related("table").order_by("-started_at"),
    })


@login_required
def journey_session(request, session_id):
    from ai_vision.models import DetectionEvent

    session = get_object_or_404(ServiceSession.objects.select_related("table"), pk=session_id, table__venue__in=_venues(request))
    events = list(DetectionEvent.objects.filter(service_session=session, experience_index__isnull=False)
                  .order_by("detected_at").values_list("detected_at", "experience_index"))
    stages = session_stages(session)
    start = session.started_at
    candidates = [stop for _, _, stop in stages] + [moment for moment, _ in events] + [start + timedelta(minutes=1)]
    end = max(candidates)
    total = max((end - start).total_seconds(), 60)

    def x(moment):
        return round(40 + 820 * max(0, (moment - start).total_seconds()) / total, 1)

    bands = []
    for key, band_start, band_stop in stages:
        readings = [float(ieo) for moment, ieo in events if band_start <= moment < band_stop]
        average = round(sum(readings) / len(readings), 1) if readings else None
        bands.append({"key": key, "label": LABELS[key], "x": x(band_start), "w": max(2, x(band_stop) - x(band_start)),
                      "minutes": round((band_stop - band_start).total_seconds() / 60), "ieo": average,
                      "emoji": emoji(average), "action": ACTIONS[key]})
    for band in bands:
        band["mid"] = round(band["x"] + band["w"] / 2, 1)
    points = [(x(moment), _y(ieo)) for moment, ieo in events]
    measured = [b for b in bands if b["ieo"] is not None]
    return render(request, "operations/journey_session.html", {
        "session": session, "bands": bands, "events": len(events),
        "polyline": " ".join(f"{px},{py}" for px, py in points), "points": points,
        "pain": min(measured, key=lambda b: b["ieo"]) if measured else None,
        "minutes": round(total / 60),
    })
