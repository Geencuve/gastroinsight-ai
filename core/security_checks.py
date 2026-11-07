"""Revisión de seguridad para el Centro de gestión: avisa de configuraciones riesgosas."""
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache

DEMO_PASSWORDS = {"admin_demo": "AdminDemo123!", "operador_demo": "OperadorDemo123!",
                  "invitado": "Invitado2026!", "admin": "Demo2026!"}


def _demo_accounts():
    cached = cache.get("gi-security-demo")
    if cached is None:
        cached = [u.username for u in User.objects.filter(username__in=DEMO_PASSWORDS, is_active=True)
                  if u.check_password(DEMO_PASSWORDS[u.username])]
        cache.set("gi-security-demo", cached, 600)
    return cached


def security_warnings():
    from authentication.models import Profile
    from cameras.models import Camera
    from privacy.models import PrivacyPolicy

    items = []
    if settings.DEBUG:
        items.append(("danger", "Modo de desarrollo activo (DEBUG)",
                      "Si ocurre un error, muestra detalles técnicos. Desactívalo al atender clientes reales."))
    if "insecure" in settings.SECRET_KEY or len(settings.SECRET_KEY) < 40:
        items.append(("danger", "Clave secreta débil", "Define una SECRET_KEY larga y aleatoria en el archivo .env."))
    for username in _demo_accounts():
        items.append(("danger", f"La cuenta «{username}» usa una contraseña de demostración conocida",
                      "Cámbiala o desactiva la cuenta: esa contraseña está publicada en el repositorio."))
    if not getattr(settings, "USE_HTTPS", False) and not settings.DEBUG:
        items.append(("warning", "Conexión sin HTTPS",
                      "Fuera de la red local, publica el sistema con HTTPS (por ejemplo, con el túnel) y USE_HTTPS=True."))
    if getattr(settings, "ALLOW_SELF_REGISTRATION", False):
        items.append(("warning", "El registro público de cuentas está abierto",
                      "Cualquiera puede crearse una cuenta. Desactívalo (ALLOW_SELF_REGISTRATION=False) salvo en un piloto controlado."))
    if not getattr(settings, "CONTACT_EMAIL", ""):
        items.append(("info", "Falta el correo de contacto", "Configura CONTACT_EMAIL para las solicitudes sobre datos personales."))
    without_venue = Profile.objects.filter(venues__isnull=True, user__is_active=True).exclude(role="platform_admin").count()
    if without_venue:
        items.append(("warning", f"{without_venue} cuenta(s) activa(s) sin local asignado",
                      "No verán datos ni alertas. Asígnales un local en la pestaña Personal."))
    venues_with_cameras = set(Camera.objects.filter(is_active=True).values_list("venue_id", flat=True))
    authorized = set(PrivacyPolicy.objects.filter(processing_enabled=True).values_list("venue_id", flat=True))
    if venues_with_cameras - authorized:
        items.append(("danger", "Hay locales con cámaras activas sin política de privacidad habilitada",
                      "El análisis visual no debe usarse sin autorización y aviso visible al público."))
    return items
