from django.urls import path

from . import views

app_name = "venues"

urlpatterns = [
    path("", views.venue_list, name="list"),
    path("nuevo/", views.venue_create, name="create"),
    path("<int:venue_id>/", views.venue_detail, name="detail"),
    path("<int:venue_id>/editar/", views.venue_edit, name="edit"),
    path("<int:venue_id>/estado/", views.venue_toggle, name="toggle"),
]