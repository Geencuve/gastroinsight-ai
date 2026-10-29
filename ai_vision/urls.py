from django.urls import path

from . import views, views_monitor, views_training

app_name = "ai_vision"

urlpatterns = [
    path("monitor/", views_monitor.monitor, name="monitor"),
    path("monitor/data/", views_monitor.monitor_data, name="monitor_data"),
    path("monitor/simulate/", views_monitor.monitor_simulate, name="monitor_simulate"),
    path("entrenamiento/", views_training.training_home, name="training"),
    path("entrenamiento/entrenar/", views_training.training_train, name="training_train"),
    path("entrenamiento/calibracion/<int:calibration_id>/", views_training.training_toggle, name="training_toggle"),
    path("entrenamiento/atencion/", views_training.training_attention, name="training_attention"),
    path("entrenamiento/muestra/<int:sample_id>/eliminar/", views_training.training_delete, name="training_delete"),
    path("entrenamiento/eliminar-todo/", views_training.training_delete_all, name="training_delete_all"),
    path("sessions/", views.session_list, name="session_list"),
    path("sessions/create/<int:camera_id>/", views.create_session, name="create_session"),
    path("sessions/<int:session_id>/start/", views.start_session, name="start_session"),
    path("sessions/<int:session_id>/stop/", views.stop_session, name="stop_session"),
    path("sessions/<int:session_id>/", views.session_detail, name="session_detail"),
    path("cameras/<int:camera_id>/preview/", views.camera_preview, name="camera_preview"),
]
