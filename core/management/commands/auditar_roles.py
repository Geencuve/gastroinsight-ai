"""
Auditoría automática de pantallas por rol (evidencia F1).
Recorre todas las direcciones sin parámetros con un usuario temporal por rol y compara el resultado con la
matriz de permisos. Todo ocurre dentro de una transacción que se deshace al final: no deja datos en la base.
"""
import csv
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.test import Client
from django.test.utils import override_settings
from django.urls import URLPattern, URLResolver, get_resolver
from django.utils import timezone

EXCLUDED = ("/admin/", "/api/", "/static/", "/media/", "/auth/logout/", "/auth/login/", "/auth/register/",
            "/gestion/acceso/", "/primer-uso/", "/__debug__/", "/i18n/")


def iter_paths(patterns, prefix=""):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            yield from iter_paths(pattern.url_patterns, prefix + str(pattern.pattern))
        elif isinstance(pattern, URLPattern):
            route = prefix + str(pattern.pattern)
            if "<" in route or "(?P" in route or route.startswith("^") or "$" in route:
                continue
            yield "/" + route


class Command(BaseCommand):
    help = "Audita el acceso de cada rol a todas las pantallas y genera la evidencia en evidencias/F1/."

    def add_arguments(self, parser):
        parser.add_argument("--salida", default="evidencias/F1")

    def handle(self, *args, **options):
        from authentication.models import Profile
        from authentication.roles import allowed_prefixes, is_path_allowed
        from venues.models import Venue

        paths = sorted({p for p in iter_paths(get_resolver().url_patterns) if not p.startswith(EXCLUDED)})
        rows = []
        # El cliente de pruebas usa el servidor «testserver»: se permite solo durante la auditoría.
        hosts = list(settings.ALLOWED_HOSTS) + ["testserver"]
        with override_settings(LEGAL_ACCEPTANCE_REQUIRED=False, DESKTOP_MODE=False, ALLOWED_HOSTS=hosts):
            with transaction.atomic():
                venues = list(Venue.objects.all())
                for role, label in Profile.Role.choices:
                    user = User.objects.create_user(f"auditoria_{role}", password=None)
                    profile, _ = Profile.objects.get_or_create(user=user)
                    profile.role = role
                    profile.save()
                    profile.venues.set(venues)
                    prefixes = allowed_prefixes(profile)
                    client = Client(raise_request_exception=True)
                    client.force_login(user)
                    for path in paths:
                        allowed = prefixes is None or is_path_allowed(path, prefixes)
                        try:
                            response = client.get(path)
                            status = response.status_code
                            location = response.get("Location", "")
                        except Exception as error:  # noqa: BLE001 — se registra como error de la pantalla
                            status, location = 500, f"{type(error).__name__}: {error}"[:180]
                        redirect_login = status in (301, 302) and "/auth/login" in location
                        if status >= 500:
                            result, detail = "ERROR", location or "Error del servidor"
                        elif status == 400:
                            result, detail = "ERROR", "Solicitud rechazada (400)"
                        elif redirect_login:
                            result, detail = "ERROR", "Perdió la sesión (redirige al inicio de sesión)"
                        elif allowed:
                            if status in (200, 301, 302, 404, 405):
                                result, detail = "OK", location
                            elif status == 403:
                                result, detail = "RESTRINGIDO", "Permiso adicional de la propia pantalla"
                            else:
                                result, detail = "ERROR", f"Respuesta inesperada ({status})"
                        elif status in (403, 301, 302, 404, 405):
                            result, detail = "OK", "Bloqueado correctamente"
                        else:
                            result, detail = "ERROR", "Visible sin permiso según la matriz de roles"
                        rows.append({"rol": label, "ruta": path, "esperado": "permitido" if allowed else "bloqueado",
                                     "estado_http": status, "resultado": result, "detalle": detail})
                    self.stdout.write(f"  {label}: {len(paths)} pantallas revisadas")
                transaction.set_rollback(True)

        folder = Path(options["salida"])
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / "auditoria_roles.csv", "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), delimiter=";")
            writer.writeheader()
            writer.writerows(rows)

        roles = list(dict.fromkeys(r["rol"] for r in rows))
        totals = Counter(r["resultado"] for r in rows)
        lines = [
            "# Auditoría de pantallas por rol (F1)", "",
            f"- Fecha: {timezone.localtime():%d-%m-%Y %H:%M}",
            f"- Versión: {getattr(settings, 'APP_VERSION', '2.0.0')}",
            f"- Pantallas por rol: {len(paths)} · Roles: {len(roles)} · Verificaciones: {len(rows)}",
            f"- Resultado: **{totals['OK']} OK**, {totals['RESTRINGIDO']} restringidas internamente, **{totals['ERROR']} errores**", "",
            "| Rol | Permitidas | Bloqueadas (403) | Restringidas | Errores |", "|---|---|---|---|---|",
        ]
        for role in roles:
            mine = [r for r in rows if r["rol"] == role]
            lines.append(f"| {role} | {sum(r['esperado'] == 'permitido' and r['resultado'] == 'OK' for r in mine)} | "
                         f"{sum(r['esperado'] == 'bloqueado' and r['resultado'] == 'OK' for r in mine)} | "
                         f"{sum(r['resultado'] == 'RESTRINGIDO' for r in mine)} | {sum(r['resultado'] == 'ERROR' for r in mine)} |")
        errors = [r for r in rows if r["resultado"] == "ERROR"]
        lines += ["", "## Errores", ""] + ([f"- **{r['rol']}** · `{r['ruta']}` · HTTP {r['estado_http']} · {r['detalle']}" for r in errors]
                                          or ["Sin errores: cada rol accede solo a lo que le corresponde y ninguna pantalla falla."])
        lines += ["", "La auditoría se ejecuta en una transacción que se deshace al terminar: no deja usuarios ni datos en la base."]
        (folder / "auditoria_roles.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

        style = self.style.SUCCESS if not errors else self.style.WARNING
        self.stdout.write(style(f"Auditoría: {totals['OK']} OK · {totals['RESTRINGIDO']} restringidas · {totals['ERROR']} errores "
                                f"→ {folder / 'auditoria_roles.md'}"))
