from django.urls import path

from . import views

app_name = "ai_vision"

urlpatterns = [
    path("sessions/", views.session_list, name="session_list"),
    path(
        "sessions/create/<int:camera_id>/",
        views.create_session,
        name="create_session",
    ),
    path(
        "sessions/<int:session_id>/start/",
        views.start_session,
        name="start_session",
    ),
    path(
        "sessions/<int:session_id>/stop/",
        views.stop_session,
        name="stop_session",
    ),
    path(
        "sessions/<int:session_id>/",
        views.session_detail,
        name="session_detail",
    ),
    path(
        "cameras/<int:camera_id>/preview/",
        views.camera_preview,
        name="camera_preview",
    ),
]