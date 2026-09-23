from django.contrib import admin

from .models import Venue


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "address",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "address")
    readonly_fields = ("created_at", "updated_at")