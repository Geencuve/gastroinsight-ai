from django.shortcuts import render
from django.utils import timezone

from analytics.views import get_accessible_venues
from authentication.permissions import get_or_create_profile

from .services.insights import build_home_summary, build_insights

SECTIONS = (
    ("ventas", "💰", "Oportunidades de venta", "Ideas para vender más con lo que ya tienes."),
    ("marketing", "📣", "Ideas de marketing", "Qué promocionar, cuándo y cómo hacerlo."),
    ("servicio", "⭐", "Mejoras en la experiencia", "Dónde mejorar la atención según tus datos."),
)


def greeting():
    hour = timezone.localtime().hour
    if hour < 12:
        return "Buenos días"
    if hour < 20:
        return "Buenas tardes"
    return "Buenas noches"


def home_view(request):
    context = {}
    if request.user.is_authenticated:
        profile = get_or_create_profile(request.user)
        venues = get_accessible_venues(profile)
        insights = build_insights(venues)
        context = {
            "greeting": greeting(),
            "today": timezone.localdate(),
            "summary": build_home_summary(venues),
            "now_items": insights["now"],
            "sections": [
                {"key": key, "icon": icon, "title": title, "subtitle": subtitle, "items": insights[key]}
                for key, icon, title, subtitle in SECTIONS
            ],
            "uses_synthetic": insights["synthetic"],
        }
    return render(request, "core/home.html", context)
