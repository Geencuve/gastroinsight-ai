import csv
import secrets
import string
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from authentication.models import Profile
from venues.models import Venue

GROUP = "Usuarios demo"
ALPHABET = string.ascii_letters + string.digits


def make_password():
    return "".join(secrets.choice(ALPHABET) for _ in range(8)) + f"-{secrets.randbelow(90) + 10}"


def resolve_role(text):
    text = (text or "").strip().lower()
    for value, label in Profile.Role.choices:
        if text in (value.lower(), label.lower()) or text in label.lower():
            return value
    return None


class Command(BaseCommand):
    help = "Crea usuarios demo para compañeros (contraseña aleatoria) o los elimina con --remove."

    def add_arguments(self, parser):
        parser.add_argument("usernames", nargs="*", help="Nombres de usuario, por ejemplo: ana pedro sofia")
        parser.add_argument("--role", default="operador", help="Rol (ver --list-roles). Por defecto: operador.")
        parser.add_argument("--password", help="Contraseña común (opcional). Si no se indica, se genera una por usuario.")
        parser.add_argument("--list-roles", action="store_true", help="Muestra los roles disponibles.")
        parser.add_argument("--remove", action="store_true", help="Elimina todos los usuarios demo creados con este comando.")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["list_roles"]:
            for value, label in Profile.Role.choices:
                self.stdout.write(f" - {label}  (valor: {value})")
            return

        group, _ = Group.objects.get_or_create(name=GROUP)
        if options["remove"]:
            users = User.objects.filter(groups=group, is_superuser=False)
            count = users.count()
            users.delete()
            self.stdout.write(self.style.SUCCESS(f"Usuarios demo eliminados: {count}"))
            return

        if not options["usernames"]:
            raise CommandError("Indica al menos un usuario. Ejemplo: python manage.py create_demo_users ana pedro")
        role = resolve_role(options["role"])
        if role is None:
            raise CommandError("Rol no reconocido. Revisa los disponibles con: --list-roles")

        venues = list(Venue.objects.filter(is_active=True))
        role_label = dict(Profile.Role.choices)[role]
        rows = []
        for raw in options["usernames"]:
            username = raw.strip().lower()
            user, created = User.objects.get_or_create(username=username, defaults={"first_name": raw.strip().capitalize()})
            if user.is_superuser:
                self.stdout.write(self.style.WARNING(f"Se omite '{username}': es superusuario."))
                continue
            password = options["password"] or make_password()
            user.set_password(password)
            user.is_staff = False
            user.save()
            user.groups.add(group)
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = role
            profile.save()
            profile.venues.set(venues)
            rows.append([username, password, role_label, "creado" if created else "actualizado"])

        output = Path(settings.BASE_DIR) / "logs" / "usuarios_demo.csv"
        output.parent.mkdir(exist_ok=True)
        with output.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(["Usuario", "Contraseña", "Rol", "Estado"])
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(f"\n{'Usuario':<16}{'Contraseña':<16}{'Rol':<26}Estado"))
        for username, password, label, state in rows:
            self.stdout.write(f"{username:<16}{password:<16}{label:<26}{state}")
        self.stdout.write(f"\nGuardado en {output} (no se sube a Git). Compártelas de forma privada.")
