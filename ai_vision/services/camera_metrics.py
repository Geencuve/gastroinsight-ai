"""Mediciones agregadas por cámara (últimos minutos), para el supervisor y el asistente Sazón."""
from datetime import timedelta

from django.db.models import Avg, Count, Max
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from cameras.models import Camera

LIVE_SECONDS = 120


def _num(value, digits=1):
    return round(float(value), digits) if value is not None else None


def camera_measurements(venues, minutes=15, zones=None):
    now = timezone.now()
    since = now - timedelta(minutes=minutes)
    rows = []
    for camera in Camera.objects.filter(venue__in=venues, is_active=True).select_related("table", "venue").order_by("name"):
        if zones is not None:
            from authentication.zones import zone_ok

            if not zone_ok(zones, camera.zone_name or (camera.table.zone_name if camera.table_id else "")):
                continue
        events = DetectionEvent.objects.filter(session__camera=camera, detected_at__gte=since)
        agg = events.aggregate(
            readings=Count("id"), people=Avg("occupancy"), ieo=Avg("experience_index"), ibe=Avg("valence"),
            attention=Avg("attention_seeking"), latency=Avg("processing_time_ms"), detector=Avg("detector_confidence"),
            scene_people=Avg("persons_detected"), scene_tables=Avg("tables_detected"),
        )
        last = DetectionEvent.objects.filter(session__camera=camera).aggregate(last=Max("detected_at"))["last"]
        session = AnalysisSession.objects.filter(camera=camera).order_by("-id").first()
        live = bool(last and (now - last).total_seconds() <= LIVE_SECONDS)
        rows.append({
            "camera": camera, "table": camera.table.code if camera.table_id else "—",
            "synthetic": camera.source_type == Camera.SourceType.DEMO,
            "status": "En vivo" if live else (session.get_status_display() if session else "Sin análisis"),
            "live": live, "last": last, "readings": agg["readings"],
            "people": _num(agg["people"]), "scene_people": _num(agg["scene_people"]), "scene_tables": _num(agg["scene_tables"]),
            "ieo": _num(agg["ieo"], 0), "ibe": _num(agg["ibe"], 2),
            "attention_pct": round(float(agg["attention"]) * 100) if agg["attention"] is not None else None,
            "latency_ms": _num(agg["latency"]), "detector": _num(agg["detector"], 2),
        })
    return rows
