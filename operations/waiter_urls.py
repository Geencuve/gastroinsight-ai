from django.urls import path

from . import views_alerts, views_pairing

app_name = "waiter"

urlpatterns = [
    path("", views_alerts.waiter_home, name="home"),
    path("panel/", views_alerts.waiter_panel, name="panel"),
    path("conectar/", views_pairing.pair_page, name="pair"),
    path("vincular/<str:token>/", views_pairing.pair_login, name="pair_login"),
]
