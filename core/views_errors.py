from django.contrib import messages
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme


def csrf_failure(request, reason=""):
    """Formulario vencido (por ejemplo, pestaña antigua): se explica y se redirige, sin página técnica."""
    if request.user.is_authenticated:
        messages.info(request, "Ya habías iniciado sesión en otra pestaña. Te llevamos al inicio.")
        return redirect("core:home")
    messages.warning(request, "La página había expirado por seguridad. Vuelve a intentarlo.")
    target = request.path if url_has_allowed_host_and_scheme(request.path, {request.get_host()}) else "/"
    return redirect(target if request.path.startswith("/auth/") else "authentication:login")
