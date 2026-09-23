from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    path(
        "",
        views.order_list,
        name="order_list",
    ),
    path(
        "create/",
        views.order_create,
        name="order_create",
    ),
    path(
        "<int:order_id>/",
        views.order_detail,
        name="order_detail",
    ),
    path(
        "<int:order_id>/items/add/",
        views.order_item_add,
        name="order_item_add",
    ),
    path(
        "<int:order_id>/items/<int:item_id>/delete/",
        views.order_item_delete,
        name="order_item_delete",
    ),
    path(
        "<int:order_id>/discount/",
        views.order_discount_update,
        name="order_discount_update",
    ),
    path(
        "<int:order_id>/confirm/",
        views.order_confirm,
        name="order_confirm",
    ),
    path(
        "<int:order_id>/pay/",
        views.order_pay,
        name="order_pay",
    ),
    path(
        "<int:order_id>/cancel/",
        views.order_cancel,
        name="order_cancel",
    ),
]