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
