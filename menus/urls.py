from django.urls import path

from . import views

app_name = "menus"

urlpatterns = [
    path("", views.menu_list, name="list"),
    path("nueva/", views.menu_create, name="create"),
    path("carta/<int:venue_id>/", views.public_menu, name="public"),
    path("<int:menu_id>/", views.menu_detail, name="detail"),
    path("<int:menu_id>/platos/nuevo/", views.dish_create, name="dish_create"),
    path("<int:menu_id>/platos/<int:dish_id>/editar/", views.dish_edit, name="dish_edit"),
    path("<int:menu_id>/dishes/<int:dish_id>/image/", views.dish_image_update, name="dish_image"),
]