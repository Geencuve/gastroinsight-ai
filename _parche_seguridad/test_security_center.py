"""Advertencias de seguridad accionables y comando configurar_env."""
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from authentication.models import Profile
from core.security_checks import security_warnings, security_warnings_detailed
from venues.models import Venue


class SecurityCenterTests(TestCase):
    def setUp(self):
        cache.clear()
        self.venue = Venue.objects.create(name="Local")

    def _user(self, name, role, password="Clave#Segura2026", venue=True):
        user = User.objects.create_user(name, password=password)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        if venue:
            profile.venues.add(self.venue)
        return user

    def test_cada_advertencia_trae_pasos_y_formato_simple_se_mantiene(self):
        self._user("admin_demo", Profile.Role.VENUE_ADMIN, password="AdminDemo123!")
        detailed = security_warnings_detailed()
        self.assertTrue(detailed)
        for w in detailed:
            self.assertTrue(w["steps"], w["title"])
            self.assertIn(w["level"], {"danger", "warning", "info"})
        self.assertEqual([t for _, t, _ in security_warnings()], [w["title"] for w in detailed])

    def test_cuenta_demo_ajena_lleva_a_editar_y_propia_a_cambiar_contrasena(self):
        demo = self._user("admin_demo", Profile.Role.VENUE_ADMIN, password="AdminDemo123!")
        other = self._user("jefe", Profile.Role.VENUE_ADMIN)
        ajena = next(w for w in security_warnings_detailed(other, {demo.pk}) if w["key"] == "demo:admin_demo")
        self.assertIn(f"/gestion/personal/{demo.pk}/", ajena["action_url"])
        propia = next(w for w in security_warnings_detailed(demo, {demo.pk}) if w["key"] == "demo:admin_demo")
        self.assertNotIn("/gestion/personal/", propia["action_url"])
        self.assertTrue(propia["action_url"])

    def test_cuentas_sin_local_se_nombran_y_llevan_a_personal(self):
        self._user("garzon_nuevo", Profile.Role.WAITER, venue=False)
        item = next(w for w in security_warnings_detailed() if w["key"] == "sin_local")
        self.assertIn("garzon_nuevo", " ".join(item["steps"]))
        self.assertEqual(item["action_tab"], 0)

    @override_settings(DEBUG=True)
    def test_debug_sugiere_comando(self):
        item = next(w for w in security_warnings_detailed() if w["key"] == "debug")
        self.assertIn("configurar_env DEBUG False", item["command"])

    def test_pantalla_muestra_advertencias_accionables(self):
        admin = self._user("jefe", Profile.Role.VENUE_ADMIN)
        self._user("garzon_nuevo", Profile.Role.WAITER, venue=False)
        self.client.force_login(admin)
        response = self.client.get("/gestion/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-sec-index")
        self.assertContains(response, "sec-fix-")


class ConfigurarEnvTests(TestCase):
    def _env(self, text):
        folder = tempfile.mkdtemp()
        path = Path(folder) / ".env"
        path.write_bytes(text.encode("utf-8"))
        return path

    def test_reemplaza_conservando_lineas_y_crlf(self):
        path = self._env("SECRET_KEY=abc\r\nDEBUG=True\r\nDB_NAME=x\r\n")
        call_command("configurar_env", "DEBUG", "false", archivo=str(path), stdout=StringIO())
        self.assertEqual(path.read_bytes().decode(), "SECRET_KEY=abc\r\nDEBUG=False\r\nDB_NAME=x\r\n")

    def test_clave_aleatoria_larga_y_sin_mostrarla(self):
        path = self._env("SECRET_KEY=corta\n")
        out = StringIO()
        call_command("configurar_env", "SECRET_KEY", aleatoria=True, archivo=str(path), stdout=out)
        value = path.read_text().strip().split("=", 1)[1]
        self.assertGreaterEqual(len(value), 60)
        self.assertNotIn(value, out.getvalue())

    def test_agrega_correo_y_rechaza_claves_no_permitidas(self):
        path = self._env("DEBUG=True\n")
        call_command("configurar_env", "CONTACT_EMAIL", "privacidad@local.cl", archivo=str(path), stdout=StringIO())
        self.assertIn("CONTACT_EMAIL=privacidad@local.cl", path.read_text())
        with self.assertRaises(CommandError):
            call_command("configurar_env", "DB_PASSWORD", "x", archivo=str(path), stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command("configurar_env", "CONTACT_EMAIL", "no-es-correo", archivo=str(path), stdout=StringIO())
