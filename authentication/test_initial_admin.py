"""Instalador: creación de la cuenta de administrador inicial."""
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class InitialAdminTests(TestCase):
    def _file(self, *lines):
        path = Path(tempfile.mkdtemp()) / "admin_inicial.txt"
        path.write_bytes(("\ufeff" + "\r\n".join(lines)).encode("utf-8"))  # igual que SaveStringsToUTF8File
        return path

    def test_crea_administrador_y_borra_el_archivo(self):
        path = self._file("dueno", "María", "maria@local.cl", "Clave#Segura2026", "0")
        call_command("crear_admin_inicial", archivo=str(path), stdout=StringIO())
        user = User.objects.get(username="dueno")
        self.assertTrue(user.is_superuser and user.check_password("Clave#Segura2026"))
        self.assertEqual(user.profile.role, "platform_admin")
        self.assertFalse(path.exists())

    def test_contrasena_debil_se_rechaza_y_no_crea_nada(self):
        path = self._file("dueno", "María", "", "12345678901", "0")
        with self.assertRaises(CommandError):
            call_command("crear_admin_inicial", archivo=str(path), stdout=StringIO())
        self.assertFalse(User.objects.filter(username="dueno").exists())
        self.assertFalse(path.exists())