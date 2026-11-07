from authentication.permissions import get_or_create_profile
from authentication.roles import allowed_prefixes, home_for


def role_scope(request):
    """Rutas visibles en el menú para el rol del usuario (None = sin restricción)."""
    if not request.user.is_authenticated:
        return {}
    profile = get_or_create_profile(request.user)
    return {"gi_role_scope": allowed_prefixes(profile), "gi_role_home": home_for(profile),
            "gi_role_label": profile.get_role_display()}
