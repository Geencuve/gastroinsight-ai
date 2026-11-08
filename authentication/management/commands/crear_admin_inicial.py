"""Crea la cuenta de administrador inicial. Lo usa el instalador de Windows.

El instalador escribe un archivo temporal con 5 líneas (usuario, nombre, correo, contraseña, demo 1/0);
este comando lo lee y lo BORRA de inmediato, para que la contraseña no quede en disco ni en la línea de comandos.
"""
from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crea la cuenta de administrador de plataforma a partir del archivo temporal del instalador."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", required=True)

    def handle(self, *args, archivo, **options):
        path = Path(archivo)
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError as error:
            raise CommandError(f"No se pudo leer el archivo del instalador: {error}")
        finally:
            try:
                path.unlink()
            except OSError:
                pass
        if len(lines) < 5:
            raise CommandError("El archivo del instalador está incompleto.")
        username, name, email = lines[0].strip(), lines[1].strip(), lines[2].strip()
        password, demo = lines[3], lines[4].strip() == "1"

        call_command("migrate", interactive=False, verbosity=0)
        if not username or " " in username:
            raise CommandError("El usuario no puede estar vacío ni tener espacios.")
        if User.objects.filter(username__iexact=username).exists():
            raise CommandError(f"Ya existe el usuario «{username}».")
        candidate = User(username=username, email=email, first_name=name)
        try:
            validate_password(password, candidate)
        except ValidationError as error:
            raise CommandError("Contraseña rechazada: " + " ".join(error.messages))

        user = User.objects.create_superuser(username=username, email=email, password=password, first_name=name)
        from authentication.models import Profile

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.stdout.write(self.style.SUCCESS(f"[OK] Administrador «{username}» creado."))
        if demo:
            self.stdout.write("Cargando datos de demostración...")
            call_command("prepare_demo")