from authentication.permissions import get_or_create_profile
from authentication.roles import allowed_prefixes, home_for


def role_scope(request):
    """Rutas visibles en el menú y sugerencias de Sazón según el rol del usuario."""
    if not request.user.is_authenticated:
        return {}
    from assistant_chat.role_scope import chips_for

    profile = get_or_create_profile(request.user)
    from django.urls import reverse

    from operations.services.notifications import kinds_for

    return {"gi_role_scope": allowed_prefixes(profile), "gi_role_home": home_for(profile),
            "gi_role_label": profile.get_role_display(), "gi_sazon_chips": chips_for(profile),
            "gi_alerts_url": reverse("alerts:feed") if kinds_for(profile) else "",
            "gi_sazon_prompts": __import__("assistant_chat.robust", fromlist=["x"]).prompts_for(request.user)}
