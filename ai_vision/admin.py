from django.contrib import admin

from .models import AnalysisSession, DetectionEvent


class DetectionEventInline(admin.TabularInline):
    model = DetectionEvent
    extra = 0
    can_delete = False
    readonly_fields = (
        "detected_at",
        "faces_count",
        "estimated_emotion",
        "confidence",
        "processing_time_ms",
    )


@admin.register(AnalysisSession)
class AnalysisSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "camera",
        "status",
        "started_at",
        "ended_at",
        "frames_processed",
        "total_faces_detected",
    )
    list_filter = (
        "status",
        "camera__venue",
    )
    search_fields = (
        "camera__name",
        "camera__venue__name",
    )
    readonly_fields = (
        "created_at",
        "started_at",
        "ended_at",
        "frames_processed",
        "total_faces_detected",
        "error_message",
    )
    inlines = [DetectionEventInline]


@admin.register(DetectionEvent)
class DetectionEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session",
        "faces_count",
        "estimated_emotion",
        "confidence",
        "detected_at",
    )
    list_filter = (
        "estimated_emotion",
        "session__camera__venue",
    )
    search_fields = (
        "session__camera__name",
        "session__camera__venue__name",
    )
    readonly_fields = (
        "detected_at",
        "processing_time_ms",
    )

from .models import CalibrationModel, TrainingSample  # noqa: E402


@admin.register(TrainingSample)
class TrainingSampleAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "label", "predicted_label", "consent_confirmed", "uploaded_by", "created_at")
    list_filter = ("kind", "label", "consent_confirmed")


@admin.register(CalibrationModel)
class CalibrationModelAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "active", "samples_count", "accuracy_before", "accuracy_after", "created_at")
    list_filter = ("kind", "active")
