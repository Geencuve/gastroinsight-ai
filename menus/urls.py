from django.urls import path

from . import views

app_name = "menus"

urlpatterns = [
    path("", views.menu_list, name="list"),
    path("<int:menu_id>/", views.menu_detail, name="detail"),
]