from django.contrib import admin

from .models import PrivacyPolicy, ProcessingAuthorization


class ProcessingAuthorizationInline(admin.TabularInline):
    model = ProcessingAuthorization
    extra = 0
    fields = (
        "source_description",
        "authorization_type",
        "status",
        "accepted_at",
        "expires_at",
        "accepted_by",
    )
    readonly_fields = ("accepted_at",)


@admin.register(PrivacyPolicy)
class PrivacyPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "venue",
        "version",
        "processing_enabled",
        "store_original_images",
        "retain_aggregated_events_days",
        "updated_at",
        "updated_by",
    )
    list_filter = (
        "processing_enabled",
        "store_original_images",
    )
    search_fields = ("venue__name", "version")
    readonly_fields = ("created_at", "updated_at")
    inlines = [ProcessingAuthorizationInline]


@admin.register(ProcessingAuthorization)
class ProcessingAuthorizationAdmin(admin.ModelAdmin):
    list_display = (
        "privacy_policy",
        "source_description",
        "status",
        "accepted_at",
        "expires_at",
        "accepted_by",
    )
    list_filter = ("status",)
    search_fields = (
        "privacy_policy__venue__name",
        "source_description",
    )
    readonly_fields = ("accepted_at",)