from django.urls import path

from . import views

app_name = "assistant_chat"

urlpatterns = [
    path(
        "customer/<int:venue_id>/",
        views.customer_chat,
        name="customer_chat",
    ),
    path(
        "customer/conversations/<int:conversation_id>/",
        views.customer_conversation,
        name="customer_conversation",
    ),
    path(
        "staff/",
        views.staff_chat,
        name="staff_chat",
    ),
    path(
        "staff/conversations/<int:conversation_id>/",
        views.staff_conversation,
        name="staff_conversation",
    ),
    path(
        "staff/conversations/<int:conversation_id>/continue/",
        views.staff_continue_conversation,
        name="staff_continue_conversation",
    ),
    path(
        "staff/widget/message/",
        views.staff_widget_message,
        name="staff_widget_message",
    ),
    path(
        "staff/widget/conversations/<int:conversation_id>/",
        views.staff_widget_history,
        name="staff_widget_history",
    ),
]