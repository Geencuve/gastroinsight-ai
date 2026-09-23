from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import AuditLog, Incident


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "venue",
        "module",
        "severity",
        "status",
        "occurred_at",
        "reviewed_by",
    )
    list_filter = (
        "severity",
        "status",
        "module",
        "venue",
    )
    search_fields = (
        "title",
        "description",
        "module",
        "venue__name",
    )
    readonly_fields = (
        "occurred_at",
        "reviewed_at",
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user",
        "action",
        "module",
        "venue",
        "description",
        "ip_address",
    )
    list_filter = (
        "action",
        "module",
        "venue",
    )
    search_fields = (
        "user__username",
        "description",
        "object_type",
        "object_id",
    )
    readonly_fields = (
        "user",
        "venue",
        "action",
        "module",
        "object_type",
        "object_id",
        "description",
        "ip_address",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False