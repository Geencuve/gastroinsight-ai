from django.urls import path

from . import views_floor

app_name = "cashier"

urlpatterns = [path("", views_floor.cashier, name="home"),
    path("boleta/<int:order_id>/", views_floor.receipt, name="receipt")]
