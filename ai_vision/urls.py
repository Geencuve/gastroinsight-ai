from django.urls import path

from . import views, views_monitor

app_name = "ai_vision"

urlpatterns = [
    path("monitor/", views_monitor.monitor, name="monitor"),
    path("monitor/data/", views_monitor.monitor_data, name="monitor_data"),
    path("monitor/simulate/", views_monitor.monitor_simulate, name="monitor_simulate"),
    path("sessions/", views.session_list, name="session_list"),
    path("sessions/create/<int:camera_id>/", views.create_session, name="create_session"),
    path("sessions/<int:session_id>/start/", views.start_session, name="start_session"),
    path("sessions/<int:session_id>/stop/", views.stop_session, name="stop_session"),
    path("sessions/<int:session_id>/", views.session_detail, name="session_detail"),
    path("cameras/<int:camera_id>/preview/", views.camera_preview, name="camera_preview"),
]
