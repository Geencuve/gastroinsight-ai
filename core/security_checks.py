"""Revisión de seguridad para el Centro de gestión: avisa de configuraciones riesgosas
y, para cada aviso, explica por qué importa, qué hacer y dónde resolverlo."""
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import NoReverseMatch, reverse

DEMO_PASSWORDS = {"admin_demo": "AdminDemo123!", "operador_demo": "OperadorDemo123!",
                  "invitado": "Invitado2026!", "admin": "Demo2026!"}

LEVEL_LABELS = {"danger": "Crítica", "warning": "Importante", "info": "Informativa"}
ENV_HINT = "Ejecútalo en PowerShell dentro de C:\\gastroinsight_ai con el entorno activado y luego reinicia el servidor."


def _demo_accounts():
    cached = cache.get("gi-security-demo")
    if cached is None:
        cached = [u.username for u in User.objects.filter(username__in=DEMO_PASSWORDS, is_active=True)
                  if u.check_password(DEMO_PASSWORDS[u.username])]
        cache.set("gi-security-demo", cached, 600)
    return cached


def _url(name, *args):
    try:
        return reverse(name, args=args)
    except NoReverseMatch:
        return ""


def _item(level, key, title, detail, why="", steps=(), command="", action_url="", action_label="",
          action_tab=None, action_mark=""):
    return {"level": level, "level_label": LEVEL_LABELS.get(level, level), "key": key, "title": title,
            "detail": detail, "why": why, "steps": list(steps), "command": command, "command_hint": ENV_HINT if command else "",
            "action_url": action_url, "action_label": action_label, "action_tab": action_tab, "action_mark": action_mark}


def security_warnings_detailed(user=None, managed_ids=None):
    """Advertencias con su solución sugerida. `user` es quien mira la pantalla y `managed_ids`
    las cuentas que puede editar (para ofrecer el botón correcto en cada caso)."""
    from authentication.models import Profile
    from cameras.models import Camera
    from privacy.models import PrivacyPolicy

    items = []
    if settings.DEBUG:
        items.append(_item(
            "danger", "debug", "Modo de desarrollo activo (DEBUG)",
            "Si ocurre un error, muestra detalles técnicos. Desactívalo al atender clientes reales.",
            why="Con DEBUG activo, una página de error muestra rutas, configuración y partes del código a cualquier visitante.",
            steps=["Ejecuta el comando de abajo: cambia DEBUG a False en el archivo .env.",
                   "Reinicia el servidor. Con «runserver», agrega --insecure para que se sigan viendo los estilos: python manage.py runserver 0.0.0.0:8000 --insecure",
                   "En la demostración local puedes dejarlo activo; desactívalo antes de atender clientes reales."],
            command="python manage.py configurar_env DEBUG False"))
    if "insecure" in settings.SECRET_KEY or len(settings.SECRET_KEY) < 40:
        items.append(_item(
            "danger", "secret_key", "Clave secreta débil",
            "Define una SECRET_KEY larga y aleatoria en el archivo .env.",
            why="La SECRET_KEY firma las sesiones y los enlaces. Si es corta o conocida, alguien podría falsificar una sesión.",
            steps=["Ejecuta el comando de abajo: genera una clave aleatoria de 60+ caracteres y la guarda en .env.",
                   "Reinicia el servidor. Las sesiones abiertas se cerrarán y cada persona deberá volver a ingresar.",
                   "No subas el archivo .env al repositorio."],
            command="python manage.py configurar_env SECRET_KEY --aleatoria"))
    demo = _demo_accounts()
    ids = dict(User.objects.filter(username__in=demo).values_list("username", "pk"))
    for username in demo:
        is_self = user is not None and getattr(user, "username", None) == username
        can_edit = managed_ids is None or ids.get(username) in managed_ids
        if is_self:
            url, label = _url("authentication:password_change"), "🔑 Cambiar mi contraseña"
            steps = ["Es tu propia cuenta: usa el botón para elegir una contraseña nueva.",
                     "Usa al menos 10 caracteres combinando letras, números y símbolos.",
                     "Esta advertencia desaparece en unos minutos (la revisión se guarda 10 min en caché)."]
        elif can_edit and ids.get(username):
            url, label = _url("management:staff_edit", ids[username]), f"✏️ Editar «{username}»"
            steps = ["Abre la ficha de la cuenta con el botón de abajo.",
                     "Escribe una contraseña nueva en «Nueva contraseña», o desmarca «Cuenta activa» si nadie la usa.",
                     "Guarda los cambios. La advertencia desaparece en unos minutos."]
        else:
            url, label = "", ""
            steps = ["No administras esta cuenta: pide al administrador de la plataforma que cambie su contraseña o la desactive."]
        items.append(_item(
            "danger", f"demo:{username}", f"La cuenta «{username}» usa una contraseña de demostración conocida",
            "Cámbiala o desactiva la cuenta: esa contraseña está publicada en el repositorio.",
            why="La contraseña aparece en el código público del proyecto, así que cualquiera podría entrar con esta cuenta.",
            steps=steps, action_url=url, action_label=label))
    if not getattr(settings, "USE_HTTPS", False) and not settings.DEBUG:
        items.append(_item(
            "warning", "https", "Conexión sin HTTPS",
            "Fuera de la red local, publica el sistema con HTTPS (por ejemplo, con el túnel) y USE_HTTPS=True.",
            why="Sin HTTPS, las contraseñas y los datos viajan sin cifrar por la red.",
            steps=["Publica el sistema con el túnel: .\\scripts\\publicar_demo.ps1",
                   "Activa las cookies seguras con el comando de abajo y reinicia el servidor.",
                   "Dentro de la red WiFi del local puede quedar sin HTTPS."],
            command="python manage.py configurar_env USE_HTTPS True"))
    if getattr(settings, "ALLOW_SELF_REGISTRATION", False):
        items.append(_item(
            "warning", "registro", "El registro público de cuentas está abierto",
            "Cualquiera puede crearse una cuenta. Desactívalo (ALLOW_SELF_REGISTRATION=False) salvo en un piloto controlado.",
            why="Una cuenta creada por un desconocido podría ver información del local.",
            steps=["Ejecuta el comando de abajo y reinicia el servidor.",
                   "Crea las cuentas del personal desde la pestaña Personal."],
            command="python manage.py configurar_env ALLOW_SELF_REGISTRATION False"))
    if not getattr(settings, "CONTACT_EMAIL", ""):
        items.append(_item(
            "info", "contacto", "Falta el correo de contacto",
            "Configura CONTACT_EMAIL para las solicitudes sobre datos personales.",
            why="Las personas deben poder pedir acceso o eliminación de sus datos personales; este correo aparece en el aviso de privacidad.",
            steps=["Reemplaza el correo del comando por el del local y ejecútalo.",
                   "Reinicia el servidor y revisa el aviso en la sección Privacidad."],
            command="python manage.py configurar_env CONTACT_EMAIL privacidad@tu-local.cl"))
    pending = (Profile.objects.filter(venues__isnull=True, user__is_active=True).exclude(role="platform_admin")
               .select_related("user"))
    names = [p.user.username for p in pending]
    if names:
        shown = ", ".join(names[:8]) + ("…" if len(names) > 8 else "")
        items.append(_item(
            "warning", "sin_local", f"{len(names)} cuenta(s) activa(s) sin local asignado",
            "No verán datos ni alertas. Asígnales un local en la pestaña Personal.",
            why="Cada pantalla filtra por local: una cuenta sin local entra al sistema, pero lo ve vacío.",
            steps=[f"Cuentas: {shown}.",
                   "Usa el botón para ir a Personal: las filas marcadas son las que faltan.",
                   "Pulsa «Editar» en cada una, elige su local y guarda."],
            action_tab=0, action_mark="sin-local", action_label="👥 Ver en Personal"))
    venues_with_cameras = set(Camera.objects.filter(is_active=True).values_list("venue_id", flat=True))
    authorized = set(PrivacyPolicy.objects.filter(processing_enabled=True).values_list("venue_id", flat=True))
    if venues_with_cameras - authorized:
        items.append(_item(
            "danger", "privacidad", "Hay locales con cámaras activas sin política de privacidad habilitada",
            "El análisis visual no debe usarse sin autorización y aviso visible al público.",
            why="El análisis visual solo es legítimo con una política aprobada y un aviso visible para los clientes.",
            steps=["Abre Privacidad y habilita la política del local.",
                   "Imprime el aviso para el público y ubícalo a la vista.",
                   "Mientras tanto, puedes desactivar las cámaras en la pestaña Cámaras."],
            action_url=_url("privacy:policy_list"), action_label="🔒 Ir a Privacidad"))
    return items


def security_warnings():
    """Formato simple (nivel, título, detalle), usado por las pruebas y otros módulos."""
    return [(w["level"], w["title"], w["detail"]) for w in security_warnings_detailed()]
