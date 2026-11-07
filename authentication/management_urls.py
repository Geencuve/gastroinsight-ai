from django.urls import path

from . import views_management

app_name = "management"

urlpatterns = [
    path("", views_management.home, name="home"),
    path("acceso/", views_management.management_login, name="login"),
    path("personal/nuevo/", views_management.staff_create, name="staff_create"),
    path("personal/<int:user_id>/", views_management.staff_edit, name="staff_edit"),
    path("mesas/nueva/", views_management.table_create, name="table_create"),
    path("camaras/nueva/", views_management.camera_create, name="camera_create"),
]
