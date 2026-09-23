from datetime import datetime, time, timedelta

from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from operations.models import SatisfactionEvaluation, ServiceSession


def parse_date(raw_date, default_date=None):
    if not raw_date:
        return default_date or timezone.localdate()

    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return default_date or timezone.localdate()


def get_date_from_request(request):
    return parse_date(request.GET.get("date"))


def get_period_from_request(request):
    period_type = request.GET.get("period", "week")

    if period_type not in ("week", "month"):
        period_type = "week"

    raw_start = request.GET.get("start")

    if raw_start:
        start_date = parse_date(
            raw_start,
            timezone.localdate(),
        )
    else:
        today = timezone.localdate()

        if period_type == "week":
            start_date = today - timedelta(days=today.weekday())
        else:
            start_date = today.replace(day=1)

    if period_type == "week":
        start_date = start_date - timedelta(
            days=start_date.weekday()
        )
        end_date = start_date + timedelta(days=7)
        period_label = (
            f"Semana del {start_date.strftime('%d-%m-%Y')} "
            f"al {(end_date - timedelta(days=1)).strftime('%d-%m-%Y')}"
        )
    else:
        start_date = start_date.replace(day=1)

        if start_date.month == 12:
            end_date = start_date.replace(
                year=start_date.year + 1,
                month=1,
                day=1,
            )
        else:
            end_date = start_date.replace(
                month=start_date.month + 1,
                day=1,
            )

        period_label = start_date.strftime("%B de %Y").capitalize()

    return {
        "period_type": period_type,
        "start_date": start_date,
        "end_date": end_date,
        "period_label": period_label,
    }


def get_datetime_range(start_date, end_date):
    start_datetime = timezone.make_aware(
        datetime.combine(start_date, time.min)
    )

    end_datetime = timezone.make_aware(
        datetime.combine(end_date, time.min)
    )

    return start_datetime, end_datetime


def get_report_data(venue, start_date, end_date):
    start_datetime, end_datetime = get_datetime_range(
        start_date,
        end_date,
    )

    service_sessions = (
        ServiceSession.objects.filter(
            table__venue=venue,
            started_at__gte=start_datetime,
            started_at__lt=end_datetime,
        )
        .select_related(
            "table",
            "table__venue",
            "created_by",
            "closed_by",
        )
        .order_by("-started_at")
    )

    analysis_sessions = (
        AnalysisSession.objects.filter(
            camera__venue=venue,
            created_at__gte=start_datetime,
            created_at__lt=end_datetime,
        )
        .select_related(
            "camera",
            "camera__venue",
        )
        .order_by("-created_at")
    )

    completed_analysis_sessions = analysis_sessions.filter(
        status=AnalysisSession.Status.COMPLETED
    )

    events = (
        DetectionEvent.objects.filter(
            session__in=completed_analysis_sessions,
            detected_at__gte=start_datetime,
            detected_at__lt=end_datetime,
        )
        .select_related(
            "session",
            "session__camera",
        )
        .order_by("detected_at")
    )

    evaluations = (
        SatisfactionEvaluation.objects.filter(
            service_session__table__venue=venue,
            created_at__gte=start_datetime,
            created_at__lt=end_datetime,
        )
        .select_related(
            "service_session",
            "service_session__table",
            "dish",
            "dish__menu",
        )
        .order_by("-created_at")
    )

    service_summary = service_sessions.aggregate(
        sessions_count=Count("id"),
        average_guests=Avg("guests_count"),
    )

    analysis_summary = completed_analysis_sessions.aggregate(
        analysis_sessions_count=Count("id"),
        frames_processed=Sum("frames_processed"),
        faces_detected=Sum("total_faces_detected"),
    )

    event_summary = events.aggregate(
        events_count=Count("id"),
        average_faces=Avg("faces_count"),
        average_processing_time=Avg("processing_time_ms"),
    )

    evaluation_summary = evaluations.aggregate(
        evaluations_count=Count("id"),
        average_rating=Avg("rating"),
    )

    cameras_summary = (
        completed_analysis_sessions.values(
            "camera__name",
            "camera__zone_name",
        )
        .annotate(
            sessions_count=Count("id"),
            frames_processed=Sum("frames_processed"),
            faces_detected=Sum("total_faces_detected"),
        )
        .order_by("camera__name")
    )

    daily_summary = (
        service_sessions.annotate(
            day=TruncDate("started_at")
        )
        .values("day")
        .annotate(
            sessions_count=Count("id"),
            average_guests=Avg("guests_count"),
        )
        .order_by("day")
    )

    evaluation_by_rating = (
        evaluations.values("rating")
        .annotate(total=Count("id"))
        .order_by("rating")
    )

    rating_map = {
        item["rating"]: item["total"]
        for item in evaluation_by_rating
    }

    rating_labels = [
        "1 - Muy insatisfecho",
        "2 - Insatisfecho",
        "3 - Neutral",
        "4 - Satisfecho",
        "5 - Muy satisfecho",
    ]

    rating_values = [
        rating_map.get(1, 0),
        rating_map.get(2, 0),
        rating_map.get(3, 0),
        rating_map.get(4, 0),
        rating_map.get(5, 0),
    ]

    return {
        "venue": venue,
        "start_date": start_date,
        "end_date": end_date,
        "service_sessions": service_sessions,
        "analysis_sessions": analysis_sessions,
        "completed_analysis_sessions": completed_analysis_sessions,
        "events": events,
        "evaluations": evaluations,
        "service_summary": service_summary,
        "analysis_summary": analysis_summary,
        "event_summary": event_summary,
        "evaluation_summary": evaluation_summary,
        "cameras_summary": cameras_summary,
        "daily_summary": daily_summary,
        "rating_labels": rating_labels,
        "rating_values": rating_values,
    }


def get_daily_report_data(venue, report_date):
    return get_report_data(
        venue=venue,
        start_date=report_date,
        end_date=report_date + timedelta(days=1),
    )