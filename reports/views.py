import csv

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from monitoring.models import AuditLog
from monitoring.services.audit import log_action
from authentication.permissions import (
    get_or_create_profile,
    user_can_access_venue,
)
from venues.models import Venue

from .services.report_data import (
    get_daily_report_data,
    get_date_from_request,
    get_period_from_request,
    get_report_data,
)


def get_authorized_venue(request, venue_id):
    venue = get_object_or_404(
        Venue,
        id=venue_id,
        is_active=True,
    )

    if not user_can_access_venue(request.user, venue):
        raise PermissionDenied(
            "No tienes permiso para consultar este local."
        )

    return venue


def add_csv_summary_rows(writer, data):
    service_summary = data["service_summary"]
    analysis_summary = data["analysis_summary"]
    event_summary = data["event_summary"]
    evaluation_summary = data["evaluation_summary"]

    writer.writerow(["Indicador", "Valor"])
    writer.writerow(
        [
            "Sesiones de atención",
            service_summary["sessions_count"] or 0,
        ]
    )
    writer.writerow(
        [
            "Promedio de comensales",
            service_summary["average_guests"] or 0,
        ]
    )
    writer.writerow(
        [
            "Sesiones de análisis completadas",
            analysis_summary["analysis_sessions_count"] or 0,
        ]
    )
    writer.writerow(
        [
            "Frames procesados",
            analysis_summary["frames_processed"] or 0,
        ]
    )
    writer.writerow(
        [
            "Rostros acumulados en frames",
            analysis_summary["faces_detected"] or 0,
        ]
    )
    writer.writerow(
        [
            "Eventos visuales registrados",
            event_summary["events_count"] or 0,
        ]
    )
    writer.writerow(
        [
            "Promedio rostros por evento",
            event_summary["average_faces"] or 0,
        ]
    )
    writer.writerow(
        [
            "Promedio procesamiento (ms)",
            event_summary["average_processing_time"] or 0,
        ]
    )
    writer.writerow(
        [
            "Evaluaciones voluntarias",
            evaluation_summary["evaluations_count"] or 0,
        ]
    )
    writer.writerow(
        [
            "Promedio evaluación voluntaria",
            evaluation_summary["average_rating"] or 0,
        ]
    )


def format_clp(value):
    return "$" + f"{int(value or 0):,}".replace(",", ".")


def add_csv_sales_rows(writer, data):
    sales = data["sales_summary"]

    writer.writerow([])
    writer.writerow(["Ventas", "Valor"])
    writer.writerow(["Pedidos pagados", sales["orders_count"] or 0])
    writer.writerow(["Ventas totales (CLP)", int(sales["revenue"])])
    writer.writerow(["Ticket promedio (CLP)", int(sales["average_ticket"])])
    writer.writerow(["Descuentos aplicados (CLP)", int(sales["discounts"])])
    writer.writerow(["Pedidos anulados", sales["cancelled_count"]])

    writer.writerow([])
    writer.writerow(["Medio de pago", "Pedidos", "Ventas (CLP)"])
    for item in data["sales_by_payment"]:
        writer.writerow([item["method"], item["orders_count"], int(item["revenue"] or 0)])

    writer.writerow([])
    writer.writerow(["Plato más vendido", "Unidades", "Ventas (CLP)"])
    for item in data["sales_top_dishes"]:
        writer.writerow([item["dish_name"], item["units"], int(item["revenue"] or 0)])

    writer.writerow([])
    writer.writerow(["Fecha", "Pedidos pagados", "Ventas (CLP)"])
    for item in data["sales_daily"]:
        writer.writerow([
            item["day"].strftime("%d-%m-%Y"),
            item["orders_count"],
            int(item["revenue"] or 0),
        ])


def build_pdf_sales_section(data, styles):
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    sales = data["sales_summary"]
    table_style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#b45309")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
    )

    summary_rows = [
        ["Indicador de ventas", "Valor"],
        ["Pedidos pagados", str(sales["orders_count"] or 0)],
        ["Ventas totales", format_clp(sales["revenue"])],
        ["Ticket promedio", format_clp(sales["average_ticket"])],
        ["Descuentos aplicados", format_clp(sales["discounts"])],
        ["Pedidos anulados", str(sales["cancelled_count"])],
    ]

    dish_rows = [["Plato más vendido", "Unidades", "Ventas"]] + [
        [item["dish_name"], str(item["units"]), format_clp(item["revenue"])]
        for item in data["sales_top_dishes"]
    ]
    if len(dish_rows) == 1:
        dish_rows.append(["Sin ventas", "0", "$0"])

    payment_rows = [["Medio de pago", "Pedidos", "Ventas"]] + [
        [item["method"], str(item["orders_count"]), format_clp(item["revenue"])]
        for item in data["sales_by_payment"]
    ]
    if len(payment_rows) == 1:
        payment_rows.append(["Sin ventas", "0", "$0"])

    elements = [Paragraph("Ventas", styles["Heading2"])]
    for rows, widths in (
        (summary_rows, [11.5 * cm, 6 * cm]),
        (dish_rows, [9.5 * cm, 3 * cm, 5 * cm]),
        (payment_rows, [9.5 * cm, 3 * cm, 5 * cm]),
    ):
        table = Table(rows, colWidths=widths)
        table.setStyle(table_style)
        elements.append(table)
        elements.append(Spacer(1, 0.4 * cm))

    elements.append(Spacer(1, 0.15 * cm))
    return elements


def build_csv_response(data, filename, title, period_label):
    response = HttpResponse(
        content_type="text/csv; charset=utf-8",
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    response.write("\ufeff")

    writer = csv.writer(response, delimiter=";")

    writer.writerow([title])
    writer.writerow(["Local", data["venue"].name])
    writer.writerow(["Período", period_label])
    writer.writerow([])

    add_csv_summary_rows(writer, data)
    add_csv_sales_rows(writer, data)

    writer.writerow([])
    writer.writerow(
        [
            "Cámara",
            "Zona",
            "Sesiones",
            "Frames",
            "Rostros acumulados",
        ]
    )

    for item in data["cameras_summary"]:
        writer.writerow(
            [
                item["camera__name"],
                item["camera__zone_name"] or "Sin zona",
                item["sessions_count"],
                item["frames_processed"] or 0,
                item["faces_detected"] or 0,
            ]
        )

    writer.writerow([])
    writer.writerow(
        [
            "Fecha",
            "Sesiones de atención",
            "Promedio de comensales",
        ]
    )

    for item in data["daily_summary"]:
        writer.writerow(
            [
                item["day"].strftime("%d-%m-%Y"),
                item["sessions_count"],
                item["average_guests"] or 0,
            ]
        )

    writer.writerow([])
    writer.writerow(
        [
            "Sesión de atención",
            "Mesa",
            "Comensales",
            "Estado",
            "Inicio",
            "Término",
        ]
    )

    for service_session in data["service_sessions"]:
        writer.writerow(
            [
                service_session.id,
                service_session.table.code,
                service_session.guests_count,
                service_session.get_status_display(),
                service_session.started_at.strftime(
                    "%d-%m-%Y %H:%M"
                ),
                (
                    service_session.ended_at.strftime(
                        "%d-%m-%Y %H:%M"
                    )
                    if service_session.ended_at
                    else ""
                ),
            ]
        )

    writer.writerow([])
    writer.writerow(
        [
            "Mesa",
            "Plato",
            "Valoración",
            "Comentario",
            "Fecha",
        ]
    )

    for evaluation in data["evaluations"]:
        writer.writerow(
            [
                evaluation.service_session.table.code,
                evaluation.dish.name if evaluation.dish else "",
                f"{evaluation.rating}/5",
                evaluation.comment,
                evaluation.created_at.strftime(
                    "%d-%m-%Y %H:%M"
                ),
            ]
        )

    return response


def build_pdf_response(data, filename, title, period_label):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    response = HttpResponse(
        content_type="application/pdf",
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    document = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=1.3 * cm,
        leftMargin=1.3 * cm,
        topMargin=1.3 * cm,
        bottomMargin=1.3 * cm,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(title, styles["Title"]))
    story.append(Spacer(1, 0.3 * cm))

    story.append(
        Paragraph(
            f"<b>Local:</b> {data['venue'].name}",
            styles["Normal"],
        )
    )

    story.append(
        Paragraph(
            f"<b>Período:</b> {period_label}",
            styles["Normal"],
        )
    )

    story.append(Spacer(1, 0.4 * cm))

    service_summary = data["service_summary"]
    analysis_summary = data["analysis_summary"]
    event_summary = data["event_summary"]
    evaluation_summary = data["evaluation_summary"]

    summary_data = [
        ["Indicador", "Valor"],
        [
            "Sesiones de atención",
            str(service_summary["sessions_count"] or 0),
        ],
        [
            "Promedio de comensales",
            f"{service_summary['average_guests'] or 0:.2f}",
        ],
        [
            "Sesiones de análisis completadas",
            str(
                analysis_summary[
                    "analysis_sessions_count"
                ]
                or 0
            ),
        ],
        [
            "Frames procesados",
            str(analysis_summary["frames_processed"] or 0),
        ],
        [
            "Rostros acumulados en frames",
            str(analysis_summary["faces_detected"] or 0),
        ],
        [
            "Eventos visuales",
            str(event_summary["events_count"] or 0),
        ],
        [
            "Promedio rostros por evento",
            f"{event_summary['average_faces'] or 0:.2f}",
        ],
        [
            "Evaluaciones voluntarias",
            str(evaluation_summary["evaluations_count"] or 0),
        ],
        [
            "Promedio de evaluación",
            f"{evaluation_summary['average_rating'] or 0:.2f}/5",
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[11.5 * cm, 6 * cm],
    )

    summary_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#1d4ed8"),
                ),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#cbd5e1"),
                ),
                (
                    "BACKGROUND",
                    (0, 1),
                    (-1, -1),
                    colors.HexColor("#f8fafc"),
                ),
                ("PADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    story.append(summary_table)
    story.append(Spacer(1, 0.55 * cm))
    story.extend(build_pdf_sales_section(data, styles))

    story.append(
        Paragraph("Resumen por cámara", styles["Heading2"])
    )

    camera_data = [
        [
            "Cámara",
            "Zona",
            "Sesiones",
            "Frames",
            "Rostros",
        ]
    ]

    for item in data["cameras_summary"]:
        camera_data.append(
            [
                item["camera__name"],
                item["camera__zone_name"] or "Sin zona",
                str(item["sessions_count"]),
                str(item["frames_processed"] or 0),
                str(item["faces_detected"] or 0),
            ]
        )

    if len(camera_data) == 1:
        camera_data.append(
            ["Sin datos", "-", "0", "0", "0"]
        )

    camera_table = Table(
        camera_data,
        colWidths=[4 * cm, 3.5 * cm, 2.5 * cm, 3.5 * cm, 3 * cm],
    )

    camera_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#0f766e"),
                ),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#cbd5e1"),
                ),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    story.append(camera_table)
    story.append(Spacer(1, 0.55 * cm))

    story.append(
        Paragraph(
            "Interpretación responsable",
            styles["Heading2"],
        )
    )

    story.append(
        Paragraph(
            (
                "Los eventos visuales corresponden a detecciones "
                "acumuladas en frames procesados; no representan "
                "personas únicas ni identifican clientes. Las "
                "evaluaciones corresponden a retroalimentación "
                "voluntaria y deben interpretarse junto con el "
                "contexto operacional."
            ),
            styles["Normal"],
        )
    )

    document.build(story)

    return response


@login_required
def report_list(request):
    profile = get_or_create_profile(request.user)

    venues = Venue.objects.filter(
        is_active=True
    ).order_by("name")

    if not profile.is_platform_admin:
        venues = venues.filter(
            assigned_profiles=profile
        )

    selected_date = get_date_from_request(request)
    period_data = get_period_from_request(request)

    return render(
        request,
        "reports/list.html",
        {
            "venues": venues,
            "selected_date": selected_date,
            "period_data": period_data,
        },
    )


@login_required
def daily_report(request, venue_id):
    venue = get_authorized_venue(request, venue_id)
    report_date = get_date_from_request(request)

    report_data = get_daily_report_data(
        venue,
        report_date,
    )

    report_data["report_title"] = "GastroInsight AI - Reporte diario"
    report_data["period_label"] = report_date.strftime(
        "%d-%m-%Y"
    )
    report_data["report_type"] = "daily"
    report_data["report_date"] = report_date

    log_action(
    request,
    action=AuditLog.Action.VIEW,
    module="reports",
    venue=venue,
    object_type="DailyReport",
    object_id=report_date.isoformat(),
    description=(
        f"Visualizó reporte diario del local "
        f"'{venue.name}' para {report_date.isoformat()}."
    ),
)
    
    return render(
        request,
        "reports/daily_report.html",
        report_data,
    )


@login_required
def daily_report_csv(request, venue_id):
    venue = get_authorized_venue(request, venue_id)
    report_date = get_date_from_request(request)

    data = get_daily_report_data(venue, report_date)

    log_action(
    request,
    action=AuditLog.Action.EXPORT,
    module="reports",
    venue=venue,
    object_type="DailyReportCSV",
    object_id=report_date.isoformat(),
    description=(
        f"Exportó reporte diario CSV del local "
        f"'{venue.name}' para {report_date.isoformat()}."
    ),
)
    
    return build_csv_response(
        data=data,
        filename=(
            f"reporte_diario_{venue.id}_"
            f"{report_date.isoformat()}.csv"
        ),
        title="GastroInsight AI - Reporte diario",
        period_label=report_date.strftime("%d-%m-%Y"),
    )


@login_required
def daily_report_pdf(request, venue_id):
    venue = get_authorized_venue(request, venue_id)
    report_date = get_date_from_request(request)

    data = get_daily_report_data(venue, report_date)

    log_action(
    request,
    action=AuditLog.Action.EXPORT,
    module="reports",
    venue=venue,
    object_type="DailyReportPDF",
    object_id=report_date.isoformat(),
    description=(
        f"Exportó reporte diario PDF del local "
        f"'{venue.name}' para {report_date.isoformat()}."
    ),
)

    return build_pdf_response(
        data=data,
        filename=(
            f"reporte_diario_{venue.id}_"
            f"{report_date.isoformat()}.pdf"
        ),
        title="GastroInsight AI - Reporte diario",
        period_label=report_date.strftime("%d-%m-%Y"),
    )


@login_required
def period_report(request, venue_id):
    venue = get_authorized_venue(request, venue_id)
    period_data = get_period_from_request(request)

    report_data = get_report_data(
        venue=venue,
        start_date=period_data["start_date"],
        end_date=period_data["end_date"],
    )

    report_data["report_title"] = (
        "GastroInsight AI - Reporte "
        + (
            "semanal"
            if period_data["period_type"] == "week"
            else "mensual"
        )
    )
    report_data["period_label"] = period_data["period_label"]
    report_data["period_type"] = period_data["period_type"]
    report_data["report_type"] = "period"

    log_action(
    request,
    action=AuditLog.Action.VIEW,
    module="reports",
    venue=venue,
    object_type=(
        "WeeklyReport"
        if period_data["period_type"] == "week"
        else "MonthlyReport"
    ),
    object_id=period_data["start_date"].isoformat(),
    description=(
        f"Visualizó reporte {period_data['period_type']} "
        f"del local '{venue.name}' para "
        f"{period_data['period_label']}."
    ))

    return render(
        request,
        "reports/period_report.html",
        report_data,
    )


@login_required
def period_report_csv(request, venue_id):
    venue = get_authorized_venue(request, venue_id)
    period_data = get_period_from_request(request)

    data = get_report_data(
        venue=venue,
        start_date=period_data["start_date"],
        end_date=period_data["end_date"],
    )

    period_name = (
        "semanal"
        if period_data["period_type"] == "week"
        else "mensual"
    )

    log_action(
    request,
    action=AuditLog.Action.EXPORT,
    module="reports",
    venue=venue,
    object_type=(
        "WeeklyReportCSV"
        if period_data["period_type"] == "week"
        else "MonthlyReportCSV"
    ),
    object_id=period_data["start_date"].isoformat(),
    description=(
        f"Exportó reporte {period_data['period_type']} "
        f"en CSV del local '{venue.name}' para "
        f"{period_data['period_label']}."))
    
    return build_csv_response(
        data=data,
        filename=(
            f"reporte_{period_name}_{venue.id}_"
            f"{period_data['start_date'].isoformat()}.csv"
        ),
        title=f"GastroInsight AI - Reporte {period_name}",
        period_label=period_data["period_label"],
    )


@login_required
def period_report_pdf(request, venue_id):
    venue = get_authorized_venue(request, venue_id)
    period_data = get_period_from_request(request)

    data = get_report_data(
        venue=venue,
        start_date=period_data["start_date"],
        end_date=period_data["end_date"],
    )

    period_name = (
        "semanal"
        if period_data["period_type"] == "week"
        else "mensual"
    )

    log_action(
    request,
    action=AuditLog.Action.EXPORT,
    module="reports",
    venue=venue,
    object_type=(
        "WeeklyReportPDF"
        if period_data["period_type"] == "week"
        else "MonthlyReportPDF"),
    object_id=period_data["start_date"].isoformat(),
    description=(
        f"Exportó reporte {period_data['period_type']} "
        f"en PDF del local '{venue.name}' para "
        f"{period_data['period_label']}."))
    
    return build_pdf_response(
        data=data,
        filename=(
            f"reporte_{period_name}_{venue.id}_"
            f"{period_data['start_date'].isoformat()}.pdf"
        ),
        title=f"GastroInsight AI - Reporte {period_name}",
        period_label=period_data["period_label"],
    )