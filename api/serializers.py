from rest_framework import serializers

from ai_vision.models import AnalysisSession, DetectionEvent
from cameras.models import Camera
from menus.models import Dish, Menu
from operations.models import (
    RestaurantTable,
    SatisfactionEvaluation,
    ServiceSession,
)
from venues.models import Venue


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = (
            "id",
            "name",
            "address",
            "description",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class MenuSerializer(serializers.ModelSerializer):
    venue_name = serializers.CharField(
        source="venue.name",
        read_only=True,
    )

    class Meta:
        model = Menu
        fields = (
            "id",
            "venue",
            "venue_name",
            "name",
            "description",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class DishSerializer(serializers.ModelSerializer):
    menu_name = serializers.CharField(
        source="menu.name",
        read_only=True,
    )
    venue_name = serializers.CharField(
        source="menu.venue.name",
        read_only=True,
    )

    class Meta:
        model = Dish
        fields = (
            "id",
            "menu",
            "menu_name",
            "venue_name",
            "name",
            "description",
            "category",
            "price",
            "is_available",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class CameraSerializer(serializers.ModelSerializer):
    venue_name = serializers.CharField(
        source="venue.name",
        read_only=True,
    )
    source_type_display = serializers.CharField(
        source="get_source_type_display",
        read_only=True,
    )

    class Meta:
        model = Camera
        fields = (
            "id",
            "venue",
            "venue_name",
            "name",
            "source_type",
            "source_type_display",
            "source",
            "zone_name",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )


class RestaurantTableSerializer(serializers.ModelSerializer):
    venue_name = serializers.CharField(
        source="venue.name",
        read_only=True,
    )

    class Meta:
        model = RestaurantTable
        fields = (
            "id",
            "venue",
            "venue_name",
            "code",
            "capacity",
            "zone_name",
            "is_active",
            "notes",
        )
        read_only_fields = ("id",)


class ServiceSessionSerializer(serializers.ModelSerializer):
    table_code = serializers.CharField(
        source="table.code",
        read_only=True,
    )
    venue_name = serializers.CharField(
        source="table.venue.name",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = ServiceSession
        fields = (
            "id",
            "table",
            "table_code",
            "venue_name",
            "status",
            "status_display",
            "started_at",
            "ended_at",
            "guests_count",
            "notes",
            "created_by",
            "closed_by",
        )
        read_only_fields = (
            "id",
            "started_at",
            "ended_at",
            "created_by",
            "closed_by",
        )


class SatisfactionEvaluationSerializer(serializers.ModelSerializer):
    table_code = serializers.CharField(
        source="service_session.table.code",
        read_only=True,
    )
    venue_name = serializers.CharField(
        source="service_session.table.venue.name",
        read_only=True,
    )
    dish_name = serializers.CharField(
        source="dish.name",
        read_only=True,
    )
    rating_display = serializers.CharField(
        source="get_rating_display",
        read_only=True,
    )

    class Meta:
        model = SatisfactionEvaluation
        fields = (
            "id",
            "service_session",
            "table_code",
            "venue_name",
            "dish",
            "dish_name",
            "rating",
            "rating_display",
            "comment",
            "created_at",
            "registered_by",
        )
        read_only_fields = (
            "id",
            "created_at",
            "registered_by",
        )


class AnalysisSessionSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(
        source="camera.name",
        read_only=True,
    )
    venue_name = serializers.CharField(
        source="camera.venue.name",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = AnalysisSession
        fields = (
            "id",
            "camera",
            "camera_name",
            "venue_name",
            "status",
            "status_display",
            "started_at",
            "ended_at",
            "frames_processed",
            "total_faces_detected",
            "error_message",
            "created_at",
        )
        read_only_fields = (
            "id",
            "started_at",
            "ended_at",
            "frames_processed",
            "total_faces_detected",
            "error_message",
            "created_at",
        )


class DetectionEventSerializer(serializers.ModelSerializer):
    camera_name = serializers.CharField(
        source="session.camera.name",
        read_only=True,
    )
    venue_name = serializers.CharField(
        source="session.camera.venue.name",
        read_only=True,
    )

    class Meta:
        model = DetectionEvent
        fields = (
            "id",
            "session",
            "camera_name",
            "venue_name",
            "detected_at",
            "faces_count",
            "estimated_emotion",
            "confidence",
            "processing_time_ms",
        )
        read_only_fields = (
            "id",
            "detected_at",
        )