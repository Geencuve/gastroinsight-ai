from django.urls import path

from . import views

app_name = "operations"

urlpatterns = [
    path("tables/", views.table_list, name="table_list"),
    path(
        "tables/create/<int:venue_id>/",
        views.table_create,
        name="table_create",
    ),
    path(
        "sessions/",
        views.service_session_list,
        name="session_list",
    ),
    path(
        "sessions/create/",
        views.service_session_create,
        name="session_create",
    ),
    path(
        "sessions/<int:session_id>/close/",
        views.service_session_close,
        name="session_close",
    ),
    path(
        "sessions/<int:session_id>/cancel/",
        views.service_session_cancel,
        name="session_cancel",
    ),
    path(
        "evaluations/",
        views.evaluation_list,
        name="evaluation_list",
    ),
    path(
        "evaluations/create/",
        views.evaluation_create,
        name="evaluation_create",
    ),
]