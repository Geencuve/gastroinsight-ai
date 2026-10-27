"""Identidad del asistente. El nombre se puede cambiar con ASSISTANT_NAME en el .env."""
from django.conf import settings

ASSISTANT_TAGLINE = "Copiloto de gestión"


def assistant_brand(request):
    return {
        "assistant_name": getattr(settings, "ASSISTANT_NAME", "Sazón"),
        "assistant_tagline": ASSISTANT_TAGLINE,
    }
