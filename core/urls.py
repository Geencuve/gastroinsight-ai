from django.urls import path

from . import views, views_promo

app_name = "core"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("promociones/", views_promo.promo_generator, name="promo_generator"),
    path("promociones/imagen/", views_promo.promo_image, name="promo_image"),
]
