from django.urls import path

from . import feedback

app_name = "feedback"

urlpatterns = [
    path("qr/", feedback.table_qr_codes, name="qr"),
    path("<str:token>/", feedback.customer_feedback, name="form"),
    path("<str:token>/gracias/", feedback.feedback_thanks, name="thanks"),
]
