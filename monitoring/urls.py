from django.urls import path

from . import views

app_name = "monitoring"

urlpatterns = [
    path("incidents/", views.incident_list, name="incident_list"),
    path(
        "incidents/<int:incident_id>/review/",
        views.incident_review,
        name="incident_review",
    ),
    path(
        "incidents/<int:incident_id>/resolve/",
        views.incident_resolve,
        name="incident_resolve",
    ),
    path("audit/", views.audit_log_list, name="audit_log_list"),
]