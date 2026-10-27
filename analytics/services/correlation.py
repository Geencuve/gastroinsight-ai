"""
Correlación entre métricas operacionales y expresiones faciales agregadas.

Unidad de análisis: la sesión de atención (una mesa atendida), con su tiempo de
servicio Ts y la distribución agregada de expresiones de los eventos asociados.
"""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta

import numpy as np
from django.db.models import Avg, Sum
from django.utils import timezone
from scipy import stats

from ai_vision.models import DetectionEvent
from cameras.models import Camera
from operations.models import SatisfactionEvaluation, ServiceSession
from sales.models import Order

POSITIVE = {"happy"}
NEGATIVE = {"sad", "angry", "disgust", "fear", "contempt"}

ANALYSES = [
    ("ts_minutes", "positive_pct", "Ts (min) vs % expresiones positivas"),
    ("ts_minutes", "negative_pct", "Ts (min) vs % expresiones negativas"),
    ("ts_minutes", "sales", "Ts (min) vs ventas de la mesa"),
    ("positive_pct", "rating", "% expresiones positivas vs valoración voluntaria (CSAT)"),
    ("ts_minutes", "rating", "Ts (min) vs valoración voluntaria (CSAT)"),
    ("ts_minutes", "ieo", "Ts (min) vs Índice de Experiencia Observable"),
    ("ieo", "rating", "Índice de Experiencia Observable vs valoración voluntaria (CSAT)"),
]


def strength_label(r):
    value = abs(r)
    if value < 0.1:
        return "despreciable"
    if value < 0.3:
        return "débil"
    if value < 0.5:
        return "moderada"
    if value < 0.7:
        return "considerable"
    return "fuerte"


def format_p(p):
    if p is None:
        return "—"
    if p < 0.0001:
        return "< 0,0001"
    return f"{p:.4f}".replace(".", ",")


def build_dataset(venues, start_date, end_date, table=None, min_detections=20, include_synthetic=True):
    start = timezone.make_aware(datetime.combine(start_date, time.min))
    end = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min))

    events = DetectionEvent.objects.filter(
        service_session__table__venue__in=venues,
        service_session__status=ServiceSession.Status.CLOSED,
        service_session__ended_at__isnull=False,
        service_session__started_at__gte=start,
        service_session__started_at__lt=end,
    )
    if table is not None:
        events = events.filter(service_session__table=table)
    if not include_synthetic:
        events = events.exclude(session__camera__source_type=Camera.SourceType.DEMO)

    distributions = defaultdict(Counter)
    synthetic = set()
    ieo_values = defaultdict(list)
    for session_id, distribution, source_type, index in events.values_list(
        "service_session_id", "emotion_distribution", "session__camera__source_type", "experience_index",
    ):
        distributions[session_id].update(distribution or {})
        if index is not None:
            ieo_values[session_id].append(float(index))
        if source_type == Camera.SourceType.DEMO:
            synthetic.add(session_id)

    ids = [sid for sid, counts in distributions.items() if sum(counts.values()) >= min_detections]

    sales = dict(
        Order.objects.filter(service_session_id__in=ids, status=Order.Status.PAID)
        .values("service_session_id").annotate(total=Sum("total"))
        .values_list("service_session_id", "total")
    )
    ratings = dict(
        SatisfactionEvaluation.objects.filter(service_session_id__in=ids)
        .values("service_session_id").annotate(avg=Avg("rating"))
        .values_list("service_session_id", "avg")
    )

    rows = []
    for session in ServiceSession.objects.filter(id__in=ids).select_related("table"):
        counts = distributions[session.id]
        total = sum(counts.values())
        rows.append({
            "session_id": session.id,
            "table": session.table.code,
            "started_at": session.started_at,
            "ts_minutes": round((session.ended_at - session.started_at).total_seconds() / 60, 1),
            "guests": session.guests_count,
            "detections": total,
            "positive_pct": round(100 * sum(counts[k] for k in POSITIVE) / total, 2),
            "negative_pct": round(100 * sum(counts[k] for k in NEGATIVE) / total, 2),
            "neutral_pct": round(100 * counts["neutral"] / total, 2),
            "sales": float(sales.get(session.id) or 0),
            "rating": float(ratings[session.id]) if session.id in ratings else None,
            "ieo": round(sum(ieo_values[session.id]) / len(ieo_values[session.id]), 2) if ieo_values[session.id] else None,
            "synthetic": session.id in synthetic,
        })
    rows.sort(key=lambda row: row["started_at"])
    return rows


def correlate(rows, x_key, y_key):
    pairs = [(r[x_key], r[y_key]) for r in rows if r[x_key] is not None and r[y_key] is not None]
    result = {
        "n": len(pairs), "pearson_r": None, "pearson_p": None, "spearman_rho": None,
        "spearman_p": None, "significant": False, "slope": None, "intercept": None,
    }
    if len(pairs) < 3:
        result["interpretation"] = "Datos insuficientes (se requieren al menos 3 sesiones)."
    else:
        x = np.array([p[0] for p in pairs], dtype=float)
        y = np.array([p[1] for p in pairs], dtype=float)
        if np.std(x) == 0 or np.std(y) == 0:
            result["interpretation"] = "Una de las variables no presenta variación."
        else:
            r, p = stats.pearsonr(x, y)
            rho, p_s = stats.spearmanr(x, y)
            slope, intercept = np.polyfit(x, y, 1)
            significant = bool(p < 0.05)
            direction = "positiva" if r > 0 else "negativa"
            text = f"Correlación {strength_label(r)} {direction}"
            text += (
                ", estadísticamente significativa (p < 0,05): se rechaza H0."
                if significant else
                ", no significativa (p ≥ 0,05): no se rechaza H0."
            )
            result.update({
                "pearson_r": float(r), "pearson_p": float(p),
                "spearman_rho": float(rho), "spearman_p": float(p_s),
                "significant": significant, "slope": float(slope),
                "intercept": float(intercept), "interpretation": text,
            })
    result["pearson_p_display"] = format_p(result["pearson_p"])
    result["spearman_p_display"] = format_p(result["spearman_p"])
    return result
