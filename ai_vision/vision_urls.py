from django.urls import path

from . import views_vision

app_name = "vision"

urlpatterns = [
    path("", views_vision.vision_home, name="home"),
    path("camaras/datos/", views_vision.vision_data, name="data"),
    path("camaras/<int:camera_id>/vivo/", views_vision.vision_live, name="live"),
]
