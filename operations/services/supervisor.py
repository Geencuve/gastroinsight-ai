"""Panel del supervisor: operación en tiempo real, cámaras, calidad del servicio e infraestructura."""
from collections import Counter
from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from ai_vision.services.camera_metrics import camera_measurements
from ai_vision.services.indices import INDEX_DEFINITIONS
from operations.models import (EnvironmentReading, InfrastructureReport, RestaurantTable, SatisfactionEvaluation,
                               ServiceSession, WaitlistEntry)


def _service_quality(venues):
    from scipy.stats import pearsonr, spearmanr

    from analytics.services.correlation import build_dataset

    today = timezone.localdate()
    result = {"n": 0, "synthetic": False}
    rows = [r for r in build_dataset(venues, today - timedelta(days=29), today, include_synthetic=False)
            if r.get("ieo") is not None and r.get("ts_minutes") is not None]
    if len(rows) < 5:
        rows = [r for r in build_dataset(venues, today - timedelta(days=29), today, include_synthetic=True)
                if r.get("ieo") is not None and r.get("ts_minutes") is not None]
        result["synthetic"] = True
    result["n"] = len(rows)
    ts, ieo = [float(r["ts_minutes"]) for r in rows], [float(r["ieo"]) for r in rows]
    if len(rows) >= 5 and len(set(ts)) > 1 and len(set(ieo)) > 1:
        r, p = pearsonr(ts, ieo)
        rho, p_s = spearmanr(ts, ieo)
        result.update({"r": round(float(r), 2), "p": float(p), "rho": round(float(rho), 2), "p_s": float(p_s),
                       "significant": p < 0.05, "ts_avg": round(sum(ts) / len(ts)), "ieo_avg": round(sum(ieo) / len(ieo))})
    return result


def build_supervisor(venues):
    now = timezone.now()
    sessions = ServiceSession.objects.filter(table__venue__in=venues, status=ServiceSession.Status.OPEN)
    tables_total = RestaurantTable.objects.filter(venue__in=venues, is_active=True).count()
    staff = (User.objects.filter(is_active=True, last_login__gte=now - timedelta(hours=12), profile__venues__in=venues)
             .select_related("profile").distinct())
    roles = Counter(user.profile.get_role_display() for user in staff)

    flow = []
    for hours_ago in range(5, -1, -1):
        end = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours_ago - 1)
        start = end - timedelta(hours=1)
        guests = ServiceSession.objects.filter(table__venue__in=venues, started_at__gte=start, started_at__lt=end) \
            .aggregate(g=Sum("guests_count"))["g"] or 0
        flow.append({"label": timezone.localtime(start).strftime("%H:00"), "value": guests})
    top = max((f["value"] for f in flow), default=0) or 1
    for f in flow:
        f["pct"] = max(2, round(100 * f["value"] / top))

    week = now - timedelta(days=7)
    infra_scores = SatisfactionEvaluation.objects.filter(
        service_session__table__venue__in=venues, service_session__started_at__gte=week,
    ).aggregate(cleanliness=Avg("cleanliness_rating"), restroom=Avg("restroom_rating"), ambience=Avg("ambience_rating"),
                value=Avg("value_rating"), answers=Count("cleanliness_rating"))
    latest_by_zone = {}
    for reading in EnvironmentReading.objects.filter(venue__in=venues, recorded_at__gte=now - timedelta(hours=24)):
        latest_by_zone.setdefault((reading.venue_id, reading.zone), reading)

    return {
        "now": now,
        "kpis": {
            "guests": sessions.aggregate(g=Sum("guests_count"))["g"] or 0,
            "occupied": sessions.count(), "tables": tables_total,
            "waiting": WaitlistEntry.objects.filter(venue__in=venues, seated_at__isnull=True, cancelled=False).count(),
            "staff": staff.count(),
        },
        "roles": sorted(roles.items()),
        "flow": flow,
        "cameras": camera_measurements(venues),
        "quality": _service_quality(venues),
        "infra_scores": infra_scores,
        "environment": list(latest_by_zone.values()),
        "reports": InfrastructureReport.objects.filter(venue__in=venues, status="open"),
        "areas": InfrastructureReport.Area.choices,
        "indices": INDEX_DEFINITIONS,
        "venues": venues,
    }
