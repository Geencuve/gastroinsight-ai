"""
Vinculación de celulares por QR: el garzón escanea un código de un solo uso (5 minutos)
y su celular queda con la sesión abierta en «Mis alertas». Solo para roles de servicio.
"""
import secrets
import socket
from datetime import timedelta

import segno
from django.conf import settings
from django.contrib.auth.models import User
from django.core import signing
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from authentication.permissions import get_or_create_profile
from authentication.roles import BAR, CASHIER, KITCHEN, OPERATOR, WAITER

PAIR_SALT = "gi-pairing"
PAIR_TTL = 300
SERVICE_ROLES = {WAITER, CASHIER, KITCHEN, BAR, OPERATOR}
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


class PairingError(Exception):
    pass


def can_pair(user):
    return user.is_active and not user.is_superuser and get_or_create_profile(user).role in SERVICE_ROLES


def make_token(user):
    nonce = secrets.token_urlsafe(9)
    cache.set(f"gi-pair-{nonce}", user.id, PAIR_TTL)
    return signing.TimestampSigner(salt=PAIR_SALT).sign(f"{user.id}:{nonce}")


def use_token(token):
    try:
        value = signing.TimestampSigner(salt=PAIR_SALT).unsign(token, max_age=PAIR_TTL)
    except signing.SignatureExpired:
        raise PairingError("El código caducó. Genera uno nuevo.")
    except signing.BadSignature:
        raise PairingError("El código no es válido.")
    user_id, _, nonce = value.partition(":")
    key = f"gi-pair-{nonce}"
    if str(cache.get(key)) != user_id:
        raise PairingError("Este código ya se usó. Genera uno nuevo.")
    cache.delete(key)
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None or not can_pair(user):
        raise PairingError("Esta cuenta no puede vincularse por QR.")
    return user


def lan_ip():
    """IP del equipo en la red local (no envía datos; solo consulta la ruta)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
    except OSError:
        return None


def base_url(request):
    configured = getattr(settings, "PUBLIC_BASE_URL", "")
    if configured:
        return configured.rstrip("/"), False
    host, _, port = request.get_host().partition(":")
    if host in LOCAL_HOSTS:
        ip = lan_ip()
        if ip:
            return f"http://{ip}:{port or '8000'}", True
    return f"{request.scheme}://{request.get_host()}", False


def pair_context(request, user):
    root, local = base_url(request)
    url = root + reverse("waiter:pair_login", args=[make_token(user)])
    return {
        "target": user, "url": url, "local_network": local, "lan_ip": lan_ip(),
        "qr_svg": mark_safe(segno.make(url, error="m").svg_inline(omitsize=True, scale=7, dark="#111111", light="#ffffff")),  # nosec B308 B703 - SVG del QR generado por el propio sistema, sin datos del usuario
        "expires_at": timezone.now() + timedelta(seconds=PAIR_TTL),
    }
