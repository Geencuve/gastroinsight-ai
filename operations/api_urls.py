from django.urls import path

from . import api

app_name = "integracion"

urlpatterns = [
    path("estado/", api.status, name="status"),
    path("telemetria/", api.telemetry, name="telemetry"),
    path("ventas/", api.sales, name="sales"),
]
