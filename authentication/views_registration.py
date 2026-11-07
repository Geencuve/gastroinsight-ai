from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect


def registration_gate(request, *args, **kwargs):
    """El producto final no tiene registro abierto: las cuentas las crea el administrador del local."""
    if getattr(settings, "ALLOW_SELF_REGISTRATION", False):
        from authentication import views

        original = getattr(views, "register_view", None) or getattr(views, "register", None)
        if original:
            return original(request, *args, **kwargs)
    messages.info(request, "Las cuentas las crea el administrador de tu local. Pídele tu usuario y contraseña.")
    return redirect("authentication:login")
