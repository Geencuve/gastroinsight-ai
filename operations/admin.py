from django.contrib import admin

from .models import RestaurantTable, ServiceSession,SatisfactionEvaluation



@admin.register(RestaurantTable)
class RestaurantTableAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "venue",
        "zone_name",
        "capacity",
        "is_active",
    )
    list_filter = (
        "venue",
        "zone_name",
        "is_active",
    )
    search_fields = (
        "code",
        "venue__name",
        "zone_name",
    )


@admin.register(ServiceSession)
class ServiceSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "table",
        "status",
        "guests_count",
        "started_at",
        "ended_at",
        "created_by",
    )
    list_filter = (
        "status",
        "table__venue",
    )
    search_fields = (
        "table__code",
        "table__venue__name",
    )
    readonly_fields = (
        "started_at",
        "ended_at",
        "created_at",
        "updated_at",
    )

@admin.register(SatisfactionEvaluation)
class SatisfactionEvaluationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "service_session",
        "dish",
        "rating",
        "created_at",
        "registered_by",
    )
    list_filter = (
        "rating",
        "service_session__table__venue",
    )
    search_fields = (
        "service_session__table__code",
        "service_session__table__venue__name",
        "dish__name",
        "comment",
    )
    readonly_fields = ("created_at",)

from .models import WaitlistEntry  # noqa: E402


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("party_name", "guests", "venue", "arrived_at", "seated_at", "cancelled")
    list_filter = ("venue", "cancelled")

from .models import EnvironmentReading, InfrastructureReport  # noqa: E402


@admin.register(EnvironmentReading)
class EnvironmentReadingAdmin(admin.ModelAdmin):
    list_display = ("zone", "venue", "lighting", "noise", "temperature_c", "recorded_at")


@admin.register(InfrastructureReport)
class InfrastructureReportAdmin(admin.ModelAdmin):
    list_display = ("area", "description", "venue", "status", "created_at")
    list_filter = ("area", "status")

from .models import Notification  # noqa: E402


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "level", "venue", "created_at", "acknowledged_by")
    list_filter = ("kind", "level")
