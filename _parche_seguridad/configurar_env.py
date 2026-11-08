"""Cambia una variable del archivo .env sin editarlo a mano (lo usan las advertencias de seguridad).

Ejemplos:
    python manage.py configurar_env DEBUG False
    python manage.py configurar_env SECRET_KEY --aleatoria
    python manage.py configurar_env CONTACT_EMAIL privacidad@mi-local.cl
"""
import re
import secrets
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

PERMITIDAS = {"DEBUG", "SECRET_KEY", "CONTACT_EMAIL", "USE_HTTPS", "ALLOW_SELF_REGISTRATION"}
BOOLEANAS = {"DEBUG", "USE_HTTPS", "ALLOW_SELF_REGISTRATION"}


def actualizar_env(ruta, clave, valor):
    """Reemplaza (o agrega) CLAVE=valor conservando el resto del archivo y sus finales de línea."""
    ruta = Path(ruta)
    texto = ruta.read_text(encoding="utf-8-sig") if ruta.exists() else ""
    salto = "\r\n" if "\r\n" in texto else "\n"
    lineas = texto.splitlines()
    patron = re.compile(rf"^\s*{re.escape(clave)}\s*=")
    reemplazada = False
    for i, linea in enumerate(lineas):
        if patron.match(linea):
            lineas[i] = f"{clave}={valor}"
            reemplazada = True
    if not reemplazada:
        lineas.append(f"{clave}={valor}")
    ruta.write_text(salto.join(lineas) + salto, encoding="utf-8")
    return reemplazada


class Command(BaseCommand):
    help = "Cambia una variable permitida del archivo .env (DEBUG, SECRET_KEY, CONTACT_EMAIL, USE_HTTPS, ALLOW_SELF_REGISTRATION)."

    def add_arguments(self, parser):
        parser.add_argument("clave")
        parser.add_argument("valor", nargs="?", default=None)
        parser.add_argument("--aleatoria", action="store_true", help="Genera un valor aleatorio (solo SECRET_KEY).")
        parser.add_argument("--archivo", default=None, help="Ruta del .env (por defecto, el de la raíz del proyecto).")

    def handle(self, *args, clave, valor, aleatoria, archivo, **options):
        clave = clave.upper()
        if clave not in PERMITIDAS:
            raise CommandError(f"Solo se pueden cambiar: {', '.join(sorted(PERMITIDAS))}.")
        if aleatoria:
            if clave != "SECRET_KEY":
                raise CommandError("--aleatoria solo sirve para SECRET_KEY.")
            valor = secrets.token_urlsafe(64)
        if valor is None:
            raise CommandError("Falta el valor (o usa --aleatoria para SECRET_KEY).")
        if clave in BOOLEANAS:
            if valor.lower() not in {"true", "false"}:
                raise CommandError(f"{clave} debe ser True o False.")
            valor = "True" if valor.lower() == "true" else "False"
        if clave == "SECRET_KEY" and len(valor) < 50:
            raise CommandError("La SECRET_KEY debe tener al menos 50 caracteres (usa --aleatoria).")
        if clave == "CONTACT_EMAIL":
            try:
                validate_email(valor)
            except ValidationError:
                raise CommandError("El correo no es válido.")
        ruta = Path(archivo) if archivo else Path(settings.BASE_DIR) / ".env"
        reemplazada = actualizar_env(ruta, clave, valor)
        mostrado = "(nueva clave aleatoria)" if clave == "SECRET_KEY" else valor
        accion = "actualizada" if reemplazada else "agregada"
        self.stdout.write(self.style.SUCCESS(f"[OK] {clave} {accion} en {ruta.name}: {mostrado}"))
        self.stdout.write("Reinicia el servidor para aplicar el cambio.")
