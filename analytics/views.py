from datetime import datetime, time, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from authentication.permissions import get_or_create_profile
from cameras.models import Camera
from operations.models import (
    RestaurantTable,
    SatisfactionEvaluation,
    ServiceSession,
)
from venues.models import Venue


def get_selected_date(request):
    raw_date = request.GET.get("date")

    if not raw_date:
        return timezone.localdate()

    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return timezone.localdate()


def get_accessible_venues(profile):
    venues = Venue.objects.filter(
        is_active=True
    ).order_by("name")

    if not profile.is_platform_admin:
        venues = venues.filter(
            assigned_profiles=profile
        )

    return venues


def get_int_filter(request, key):
    raw_value = request.GET.get(key)

    if not raw_value:
        return None

    try:
        return int(raw_value)
    except ValueError:
        return None


@login_required
def dashboard_view(request):
    profile = get_or_create_profile(request.user)

    selected_date = get_selected_date(request)
    selected_venue_id = get_int_filter(request, "venue")
    selected_table_id = get_int_filter(request, "table")
    selected_camera_id = get_int_filter(request, "camera")
    selected_service_session_id = get_int_filter(
        request,
        "service_session",
    )

    day_start = timezone.make_aware(
        datetime.combine(selected_date, time.min)
    )
    day_end = day_start + timedelta(days=1)

    accessible_venues = get_accessible_venues(profile)

    if selected_venue_id:
        selected_venue = accessible_venues.filter(
            id=selected_venue_id
        ).first()
    else:
        selected_venue = None

    tables = RestaurantTable.objects.filter(
        venue__in=accessible_venues,
        is_active=True,
    ).select_related("venue").order_by(
        "venue__name",
        "code",
    )

    cameras = Camera.objects.filter(
        venue__in=accessible_venues,
        is_active=True,
    ).select_related("venue").order_by(
        "venue__name",
        "name",
    )

    service_sessions = ServiceSession.objects.filter(
        table__venue__in=accessible_venues,
    ).select_related(
        "table",
        "table__venue",
    ).order_by("-started_at")

    if selected_venue:
        tables = tables.filter(venue=selected_venue)
        cameras = cameras.filter(venue=selected_venue)
        service_sessions = service_sessions.filter(
            table__venue=selected_venue
        )

    if selected_table_id:
        selected_table = tables.filter(
            id=selected_table_id
        ).first()
    else:
        selected_table = None

    if selected_camera_id:
        selected_camera = cameras.filter(
            id=selected_camera_id
        ).first()
    else:
        selected_camera = None

    if selected_service_session_id:
        selected_service_session = service_sessions.filter(
            id=selected_service_session_id
        ).first()
    else:
        selected_service_session = None

    filtered_service_sessions = service_sessions.filter(
        started_at__gte=day_start,
        started_at__lt=day_end,
    )

    if selected_table:
        filtered_service_sessions = filtered_service_sessions.filter(
            table=selected_table
        )

    if selected_service_session:
        filtered_service_sessions = filtered_service_sessions.filter(
            id=selected_service_session.id
        )

    analysis_sessions = AnalysisSession.objects.filter(
        camera__venue__in=accessible_venues,
        created_at__gte=day_start,
        created_at__lt=day_end,
    ).select_related(
        "camera",
        "camera__venue",
    )

    if selected_venue:
        analysis_sessions = analysis_sessions.filter(
            camera__venue=selected_venue
        )

    if selected_camera:
        analysis_sessions = analysis_sessions.filter(
            camera=selected_camera
        )

    completed_analysis_sessions = analysis_sessions.filter(
        status=AnalysisSession.Status.COMPLETED
    )

    events = DetectionEvent.objects.filter(
        session__in=completed_analysis_sessions,
        detected_at__gte=day_start,
        detected_at__lt=day_end,
    ).select_related(
        "session",
        "session__camera",
        "session__camera__venue",
    )

    evaluations = SatisfactionEvaluation.objects.filter(
        service_session__table__venue__in=accessible_venues,
        created_at__gte=day_start,
        created_at__lt=day_end,
    ).select_related(
        "service_session",
        "service_session__table",
        "service_session__table__venue",
        "dish",
    )

    if selected_venue:
        evaluations = evaluations.filter(
            service_session__table__venue=selected_venue
        )

    if selected_table:
        evaluations = evaluations.filter(
            service_session__table=selected_table
        )

    if selected_service_session:
        evaluations = evaluations.filter(
            service_session=selected_service_session
        )

    service_summary = filtered_service_sessions.aggregate(
        service_sessions_count=Count("id"),
        open_service_sessions=Count(
            "id",
            filter=Q(status=ServiceSession.Status.OPEN),
        ),
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

    sessions_by_camera = (
        completed_analysis_sessions.values(
            "camera__venue__name",
            "camera__name",
        )
        .annotate(
            sessions_count=Count("id"),
            frames_processed=Sum("frames_processed"),
            faces_detected=Sum("total_faces_detected"),
        )
        .order_by(
            "camera__venue__name",
            "camera__name",
        )
    )

    evaluations_by_rating = (
        evaluations.values("rating")
        .annotate(total=Count("id"))
        .order_by("rating")
    )

    ratings_map = {
        item["rating"]: item["total"]
        for item in evaluations_by_rating
    }

    rating_labels = [
        "1 - Muy insatisfecho",
        "2 - Insatisfecho",
        "3 - Neutral",
        "4 - Satisfecho",
        "5 - Muy satisfecho",
    ]

    rating_values = [
        ratings_map.get(1, 0),
        ratings_map.get(2, 0),
        ratings_map.get(3, 0),
        ratings_map.get(4, 0),
        ratings_map.get(5, 0),
    ]

    chart_events = events.order_by("detected_at")[:100]

    chart_labels = [
        event.detected_at.strftime("%H:%M:%S")
        for event in chart_events
    ]

    chart_faces = [
        event.faces_count
        for event in chart_events
    ]

    recent_service_sessions = filtered_service_sessions.order_by(
        "-started_at"
    )[:10]

    recent_analysis_sessions = analysis_sessions.order_by(
        "-created_at"
    )[:10]

    context = {
        "selected_date": selected_date,
        "selected_venue_id": selected_venue_id or "",
        "selected_table_id": selected_table_id or "",
        "selected_camera_id": selected_camera_id or "",
        "selected_service_session_id": (
            selected_service_session_id or ""
        ),
        "venues": accessible_venues,
        "tables": tables,
        "cameras": cameras,
        "service_sessions": service_sessions[:100],
        "selected_venue": selected_venue,
        "selected_table": selected_table,
        "selected_camera": selected_camera,
        "selected_service_session": selected_service_session,
        "service_summary": service_summary,
        "analysis_summary": analysis_summary,
        "event_summary": event_summary,
        "evaluation_summary": evaluation_summary,
        "sessions_by_camera": sessions_by_camera,
        "recent_service_sessions": recent_service_sessions,
        "recent_analysis_sessions": recent_analysis_sessions,
        "chart_labels": chart_labels,
        "chart_faces": chart_faces,
        "rating_labels": rating_labels,
        "rating_values": rating_values,
    }

    return render(
        request,
        "analytics/dashboard.html",
        context,
    )