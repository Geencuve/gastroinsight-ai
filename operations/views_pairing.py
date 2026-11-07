from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from authentication.permissions import get_or_create_profile
from authentication.roles import home_for
from monitoring.models import AuditLog
from monitoring.services.audit import log_action

from .services.pairing import PairingError, can_pair, pair_context, use_token


@login_required
def pair_page(request):
    if not can_pair(request.user):
        raise PermissionDenied("La vinculación por QR es para cuentas de servicio (garzón, caja, cocina, barra u operador).")
    log_action(request, action=AuditLog.Action.CREATE, module="authentication", object_type="Pairing",
               object_id=str(request.user.pk), description="Generó un código QR para conectar su celular.")
    return render(request, "operations/pair.html", pair_context(request, request.user))


def pair_login(request, token):
    try:
        user = use_token(token)
    except PairingError as error:
        return render(request, "operations/pair_invalid.html", {"reason": str(error)}, status=400)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    log_action(request, action=AuditLog.Action.LOGIN, module="authentication", object_type="Pairing",
               object_id=str(user.pk), description=f"Vinculó un celular por QR ({user.get_username()}).")
    messages.success(request, "Celular conectado. Aquí te llegarán las alertas de tus mesas.")
    return redirect(home_for(get_or_create_profile(user)))
