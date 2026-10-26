from django.urls import path

from . import views

app_name = "analytics"

from . import correlation_views

urlpatterns = [
    path("correlation/", correlation_views.correlation_view, name="correlation"),
    path("correlation/csv/", correlation_views.correlation_csv, name="correlation_csv"),
    path("", views.dashboard_view, name="dashboard"),
]