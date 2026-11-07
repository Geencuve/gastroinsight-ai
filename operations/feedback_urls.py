from django.urls import path

from . import feedback, views_floor

app_name = "feedback"

urlpatterns = [
    path("qr/", feedback.table_qr_codes, name="qr"),
    path("atencion/<str:token>/", views_floor.session_feedback, name="session_form"),
    path("<str:token>/", feedback.customer_feedback, name="form"),
    path("<str:token>/gracias/", feedback.feedback_thanks, name="thanks"),
]
