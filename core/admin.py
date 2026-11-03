from django.contrib import admin

# Register your models here.

admin.site.site_header = "GastroInsight AI · Administración"
admin.site.site_title = "GastroInsight AI"
admin.site.index_title = "Panel de administración"

from .models import LegalAcceptance  # noqa: E402


@admin.register(LegalAcceptance)
class LegalAcceptanceAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "version", "accepted_at", "ip_address")
    list_filter = ("version",)
    search_fields = ("user__username", "full_name")
