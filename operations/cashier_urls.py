from django.urls import path

from . import views_floor

app_name = "cashier"

urlpatterns = [path("", views_floor.cashier, name="home")]
