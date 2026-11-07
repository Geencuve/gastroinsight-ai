from django.urls import path

from . import views_alerts

app_name = "alerts"

urlpatterns = [
    path("", views_alerts.feed, name="feed"),
    path("<int:pk>/voy/", views_alerts.acknowledge, name="ack"),
]
