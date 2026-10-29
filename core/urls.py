from django.urls import path

from . import views, views_promo, views_setup

app_name = "core"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("primer-uso/", views_setup.first_run, name="first_run"),
    path("promociones/", views_promo.promo_generator, name="promo_generator"),
    path("promociones/imagen/", views_promo.promo_image, name="promo_image"),
]
