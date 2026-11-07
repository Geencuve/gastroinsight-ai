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


# ---------------- Seguridad (I1) ----------------
LOGIN_PATHS = ("/auth/login/", "/gestion/acceso/")
USER_MAX_FAILS, IP_MAX_FAILS, LOCK_SECONDS = 5, 20, 15 * 60


def _bump(cache, key, timeout):
    if not cache.add(key, 1, timeout):
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout)


class LoginThrottleMiddleware:
    """Bloquea 15 minutos tras 5 intentos fallidos por usuario o 20 por equipo (defensa ante bots)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != "POST" or request.path not in LOGIN_PATHS:
            return self.get_response(request)
        from django.core.cache import cache
        from django.shortcuts import render

        ip = request.META.get("REMOTE_ADDR", "")
        username = (request.POST.get("username") or "").strip().lower()[:150]
        user_key, ip_key = f"gi-login-user-{username}", f"gi-login-ip-{ip}"
        if (cache.get(user_key) or 0) >= USER_MAX_FAILS or (cache.get(ip_key) or 0) >= IP_MAX_FAILS:
            try:
                from monitoring.models import AuditLog
                from monitoring.services.audit import log_action

                log_action(request, action=AuditLog.Action.LOGIN, module="authentication",
                           description=f"Acceso bloqueado por intentos fallidos (usuario «{username}», IP {ip}).")
            except Exception:  # noqa: BLE001 — el bloqueo debe aplicarse aunque falle el registro
                pass
            return render(request, "core/login_locked.html", {"minutes": LOCK_SECONDS // 60}, status=429)
        response = self.get_response(request)
        if response.status_code == 200:
            _bump(cache, user_key, LOCK_SECONDS)
            _bump(cache, ip_key, LOCK_SECONDS)
        elif response.status_code in (301, 302):
            cache.delete(user_key)
        return response


class AssistantThrottleMiddleware:
    """Sazón: máximo 30 consultas por minuto por usuario y 600 caracteres por mensaje."""

    LIMIT, WINDOW, MAX_CHARS = 30, 60, 600

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path.startswith("/assistant/") and request.user.is_authenticated:
            from django.core.cache import cache
            from django.http import JsonResponse

            message = request.POST.get("message", "")
            if len(message) > self.MAX_CHARS:
                return JsonResponse({"error": f"La consulta supera los {self.MAX_CHARS} caracteres."}, status=400)
            key = f"gi-sazon-{request.user.pk}"
            _bump(cache, key, self.WINDOW)
            if (cache.get(key) or 0) > self.LIMIT:
                return JsonResponse({"error": "Demasiadas consultas seguidas. Espera un minuto e inténtalo de nuevo."},
                                    status=429)
        return self.get_response(request)


class SecurityHeadersMiddleware:
    """Cabeceras adicionales: las páginas no pueden pedir cámara, micrófono ni ubicación al navegador."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        return response
