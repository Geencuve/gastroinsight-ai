from django.urls import path

from . import views_alerts

app_name = "waiter"

urlpatterns = [
    path("", views_alerts.waiter_home, name="home"),
    path("panel/", views_alerts.waiter_panel, name="panel"),
]
