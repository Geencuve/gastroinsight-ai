from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_list, name="list"),

    path(
        "daily/<int:venue_id>/",
        views.daily_report,
        name="daily",
    ),
    path(
        "daily/<int:venue_id>/csv/",
        views.daily_report_csv,
        name="daily_csv",
    ),
    path(
        "daily/<int:venue_id>/pdf/",
        views.daily_report_pdf,
        name="daily_pdf",
    ),

    path(
        "period/<int:venue_id>/",
        views.period_report,
        name="period",
    ),
    path(
        "period/<int:venue_id>/csv/",
        views.period_report_csv,
        name="period_csv",
    ),
    path(
        "period/<int:venue_id>/pdf/",
        views.period_report_pdf,
        name="period_pdf",
    ),
]