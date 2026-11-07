from authentication.permissions import get_or_create_profile
from authentication.roles import allowed_prefixes, home_for


def role_scope(request):
    """Rutas visibles en el menú y sugerencias de Sazón según el rol del usuario."""
    if not request.user.is_authenticated:
        return {}
    from assistant_chat.role_scope import chips_for

    profile = get_or_create_profile(request.user)
    return {"gi_role_scope": allowed_prefixes(profile), "gi_role_home": home_for(profile),
            "gi_role_label": profile.get_role_display(), "gi_sazon_chips": chips_for(profile)}
