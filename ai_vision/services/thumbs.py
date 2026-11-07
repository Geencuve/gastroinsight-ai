"""Datos de las miniaturas esquemáticas por cámara (coordenadas y métricas; nunca imágenes)."""


def camera_thumbs(venues, zones=None, limit=None):
    from ai_vision.models import AnalysisSession, DetectionEvent
    from ai_vision.services.camera_metrics import camera_measurements

    items = []
    for row in camera_measurements(venues, zones=zones):
        camera = row["camera"]
        last = (DetectionEvent.objects.filter(session__camera=camera).order_by("-detected_at")
                .values("scene_boxes", "occupancy").first()) or {}
        items.append({
            "id": camera.id, "name": camera.name, "table": row["table"],
            "zone": camera.zone_name or (camera.table.zone_name if camera.table_id else ""),
            "live": row["live"], "status": row["status"], "ieo": row["ieo"], "ibe": row["ibe"],
            "attention_pct": row["attention_pct"], "people": row["people"], "scene_people": row["scene_people"],
            "latency_ms": row["latency_ms"], "boxes": last.get("scene_boxes") or [],
            "occupancy": float(last["occupancy"]) if last.get("occupancy") is not None else None,
            "is_entrance": camera.is_entrance, "is_checkout": camera.is_checkout, "synthetic": row["synthetic"],
            "running": AnalysisSession.objects.filter(camera=camera, status=AnalysisSession.Status.RUNNING).exists(),
        })
        if limit and len(items) >= limit:
            break
    return items
