from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "role",
        "get_venues",
        "phone",
        "created_at",
    )
    list_filter = ("role",)
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
    )
    filter_horizontal = ("venues",)
    readonly_fields = (
        "created_at",
        "updated_at",
    )

    @admin.display(description="Locales asignados")
    def get_venues(self, obj):
        return ", ".join(
            venue.name for venue in obj.venues.all()
        ) or "Sin locales asignados"