from django.contrib import admin

from .models import Camera


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "venue",
        "source_type",
        "zone_name",
        "is_active",
        "updated_at",
    )
    list_filter = (
        "source_type",
        "is_active",
        "venue",
    )
    search_fields = (
        "name",
        "venue__name",
        "zone_name",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )