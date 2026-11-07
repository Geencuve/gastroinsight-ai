from django.conf import settings
from django.shortcuts import redirect

ALLOWED_PREFIXES = ("/primer-uso/", "/static/", "/media/")


class FirstRunMiddleware:
    """En la versión de escritorio, lleva al asistente de primer uso si aún no hay administrador."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.ready = False

    def __call__(self, request):
        if getattr(settings, "DESKTOP_MODE", False) and not self.ready:
            from django.contrib.auth.models import User

            if User.objects.filter(is_superuser=True).exists():
                self.ready = True
            elif not request.path.startswith(ALLOWED_PREFIXES):
                return redirect("core:first_run")
        return self.get_response(request)


LEGAL_EXEMPT = ("/legal/", "/static/", "/media/", "/auth/logout/", "/primer-uso/", "/opinion/",
                "/menus/carta/", "/assistant/customer/")


class LegalAcceptanceMiddleware:
    """Exige la toma de conocimiento de uso educativo antes de usar el sistema."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (getattr(settings, "LEGAL_ACCEPTANCE_REQUIRED", False) and request.user.is_authenticated
                and not request.path.startswith(LEGAL_EXEMPT)):
            from core.legal import LEGAL_VERSION

            key = f"legal_ok_{LEGAL_VERSION}"
            if not request.session.get(key):
                from core.models import LegalAcceptance

                if LegalAcceptance.objects.filter(user=request.user, version=LEGAL_VERSION).exists():
                    request.session[key] = True
                else:
                    from urllib.parse import urlencode

                    from django.urls import reverse

                    query = urlencode({"next": request.get_full_path()})
                    return redirect(f"{reverse('core:legal_acceptance')}?{query}")
        return self.get_response(request)


class RoleScopeMiddleware:
    """Aplica la matriz de roles: cada rol restringido solo abre las secciones que le corresponden."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            from django.shortcuts import render

            from authentication.permissions import get_or_create_profile
            from authentication.roles import allowed_prefixes, home_for, is_path_allowed

            profile = get_or_create_profile(request.user)
            prefixes = allowed_prefixes(profile)
            if request.path == "/" and prefixes is not None and home_for(profile) != "/":
                from django.shortcuts import redirect

                return redirect(home_for(profile))
            if not is_path_allowed(request.path, prefixes):
                return render(request, "core/forbidden_role.html",
                              {"role": profile.get_role_display(), "home": home_for(profile)}, status=403)
        return self.get_response(request)
