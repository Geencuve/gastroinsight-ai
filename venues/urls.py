from django.urls import path

from . import views

app_name = "venues"

urlpatterns = [
    path("", views.venue_list, name="list"),
]