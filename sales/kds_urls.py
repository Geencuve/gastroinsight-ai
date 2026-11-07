from django.urls import path

from . import views_kitchen

app_name = "kds"

urlpatterns = [
    path("", views_kitchen.station_view, name="home"),
    path("tablero/", views_kitchen.station_board, name="board"),
    path("avanzar/", views_kitchen.station_advance, name="advance"),
]
