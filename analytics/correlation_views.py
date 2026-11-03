import csv
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from authentication.permissions import get_or_create_profile
from monitoring.models import AuditLog
from monitoring.services.audit import log_action
from operations.models import RestaurantTable

from .services.correlation import ANALYSES, build_dataset, correlate
from .views import get_accessible_venues, get_int_filter


def _parse_date(raw, default):
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date() if raw else default
    except ValueError:
        return default


def _build_context(request):
    profile = get_or_create_profile(request.user)
    venues = get_accessible_venues(profile)
    today = timezone.localdate()
    start_date = _parse_date(request.GET.get("start"), today - timedelta(days=30))
    end_date = _parse_date(request.GET.get("end"), today)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    venue_id = get_int_filter(request, "venue")
    selected_venue = venues.filter(id=venue_id).first() if venue_id else None
    scope = venues.filter(id=selected_venue.id) if selected_venue else venues

    tables = RestaurantTable.objects.filter(venue__in=scope, is_active=True).order_by("venue__name", "code")
    table_id = get_int_filter(request, "table")
    selected_table = tables.filter(id=table_id).first() if table_id else None

    min_detections = min(max(get_int_filter(request, "min") or 20, 1), 1000)
    # v1.0.2: por defecto se excluyen las cámaras demo (datos sintéticos); se incluyen con ?synthetic=1
    include_synthetic = request.GET.get("synthetic", "0") == "1"

    rows = build_dataset(scope, start_date, end_date, selected_table, min_detections, include_synthetic)
    results = [
        {**correlate(rows, x_key, y_key), "label": label, "x_key": x_key, "y_key": y_key}
        for x_key, y_key, label in ANALYSES
    ]

    def scatter(result):
        points = [{"x": r[result["x_key"]], "y": r[result["y_key"]]}
                  for r in rows if r[result["y_key"]] is not None]
        trend = []
        if result["slope"] is not None and points:
            xs = [p["x"] for p in points]
            trend = [{"x": x, "y": round(result["slope"] * x + result["intercept"], 2)} for x in (min(xs), max(xs))]
        return {"points": points, "trend": trend}

    synthetic_count = sum(1 for r in rows if r["synthetic"])
    return {
        "venues": venues,
        "tables": tables,
        "selected_venue_id": str(venue_id or ""),
        "selected_table_id": str(table_id or ""),
        "selected_venue": selected_venue,
        "start_date": start_date,
        "end_date": end_date,
        "min_detections": min_detections,
        "include_synthetic": include_synthetic,
        "rows": rows,
        "results": results,
        "synthetic_count": synthetic_count,
        "real_count": len(rows) - synthetic_count,
        "chart_positive": scatter(results[0]),
        "chart_negative": scatter(results[1]),
    }


@login_required
def correlation_view(request):
    return render(request, "analytics/correlation.html", _build_context(request))


def _fmt(value, decimals=4):
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{decimals}f}".replace(".", ",")
    return value


@login_required
def correlation_csv(request):
    context = _build_context(request)
    start, end = context["start_date"], context["end_date"]
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="correlacion_{start:%Y%m%d}_{end:%Y%m%d}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")

    writer.writerow(["GastroInsight AI - Panel de correlación"])
    writer.writerow(["Período", f"{start:%d-%m-%Y} a {end:%d-%m-%Y}"])
    writer.writerow(["Sesiones analizadas", len(context["rows"])])
    writer.writerow(["Sesiones con datos sintéticos de demostración", context["synthetic_count"]])
    writer.writerow([])
    writer.writerow(["Análisis", "n", "Pearson r", "p (Pearson)", "Spearman rho", "p (Spearman)", "Interpretación"])
    for result in context["results"]:
        writer.writerow([
            result["label"], result["n"], _fmt(result["pearson_r"]), _fmt(result["pearson_p"], 6),
            _fmt(result["spearman_rho"]), _fmt(result["spearman_p"], 6), result["interpretation"],
        ])
    writer.writerow([])
    writer.writerow(["Sesión", "Mesa", "Inicio", "Ts (min)", "Comensales", "Detecciones",
                     "% positivas", "% negativas", "% neutral", "Ventas (CLP)", "Valoración", "IEO", "Origen"])
    for row in context["rows"]:
        writer.writerow([
            row["session_id"], row["table"], timezone.localtime(row["started_at"]).strftime("%d-%m-%Y %H:%M"),
            _fmt(row["ts_minutes"], 1), row["guests"], row["detections"],
            _fmt(row["positive_pct"], 2), _fmt(row["negative_pct"], 2), _fmt(row["neutral_pct"], 2),
            int(row["sales"]), _fmt(row["rating"], 2), _fmt(row["ieo"], 1), "Sintético" if row["synthetic"] else "Real",
        ])

    venue = context["selected_venue"] or context["venues"].first()
    if venue is not None:
        log_action(
            request, action=AuditLog.Action.EXPORT, module="analytics", venue=venue,
            object_type="CorrelationCSV", object_id=f"{start:%Y%m%d}-{end:%Y%m%d}",
            description=f"Exportó el panel de correlación para el período {start:%d-%m-%Y} a {end:%d-%m-%Y}.",
        )
    return response
