from django.urls import path

from . import views

app_name = "menus"

urlpatterns = [
    path("", views.menu_list, name="list"),
    path("carta/<int:venue_id>/", views.public_menu, name="public"),
    path("<int:menu_id>/", views.menu_detail, name="detail"),
    path("<int:menu_id>/dishes/<int:dish_id>/image/", views.dish_image_update, name="dish_image"),
]
