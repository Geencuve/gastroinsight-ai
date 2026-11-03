from django.urls import path

from . import views, views_legal, views_promo, views_setup

app_name = "core"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("primer-uso/", views_setup.first_run, name="first_run"),
    path("legal/acerca/", views_legal.legal_page, {"slug": "acerca"}, name="legal_about"),
    path("legal/terminos/", views_legal.legal_page, {"slug": "terminos"}, name="legal_terms"),
    path("legal/privacidad/", views_legal.legal_page, {"slug": "privacidad"}, name="legal_privacy"),
    path("legal/uso-educativo/", views_legal.legal_page, {"slug": "uso-educativo"}, name="legal_education"),
    path("legal/contacto/", views_legal.legal_page, {"slug": "contacto"}, name="legal_contact"),
    path("legal/toma-de-conocimiento/", views_legal.acceptance, name="legal_acceptance"),
    path("promociones/", views_promo.promo_generator, name="promo_generator"),
    path("promociones/imagen/", views_promo.promo_image, name="promo_image"),
]
