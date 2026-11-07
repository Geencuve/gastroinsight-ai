from django.urls import path

from . import views_floor

app_name = "floor"

urlpatterns = [
    path("", views_floor.floor_map, name="map"),
    path("tablero/", views_floor.floor_board, name="board"),
    path("espera/", views_floor.waitlist_add, name="waitlist_add"),
    path("espera/<int:entry_id>/asignar/", views_floor.waitlist_seat, name="waitlist_seat"),
    path("espera/<int:entry_id>/cancelar/", views_floor.waitlist_cancel, name="waitlist_cancel"),
    path("atencion/<int:session_id>/cuenta/", views_floor.toggle_bill, name="toggle_bill"),
    path("atencion/<int:session_id>/qr/", views_floor.session_qr, name="session_qr"),
]
