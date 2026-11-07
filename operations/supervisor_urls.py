from django.urls import path

from . import views_supervisor

app_name = "supervisor"

from . import views_journey  # noqa: E402

urlpatterns = [
    path("journey/", views_journey.journey_overview, name="journey"),
    path("journey/<int:session_id>/", views_journey.journey_session, name="journey_session"),
    path("", views_supervisor.dashboard, name="home"),
    path("ambiente/", views_supervisor.add_environment, name="add_environment"),
    path("infraestructura/", views_supervisor.add_report, name="add_report"),
    path("infraestructura/<int:report_id>/resolver/", views_supervisor.resolve_report, name="resolve_report"),
]
