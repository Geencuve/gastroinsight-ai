from django.urls import path

from . import views

app_name = "privacy"

urlpatterns = [
    path("", views.policy_list, name="policy_list"),
    path(
        "policy/<int:venue_id>/",
        views.policy_edit,
        name="policy_edit",
    ),
    path(
        "policy/<int:venue_id>/authorization/create/",
        views.authorization_create,
        name="authorization_create",
    ),
]