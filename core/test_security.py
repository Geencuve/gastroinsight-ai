from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from authentication.models import Profile
from core.security_checks import security_warnings
from venues.models import Venue


class SecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.venue = Venue.objects.create(name="Local")

    def _user(self, name, role, password="Clave#Segura2026"):
        user = User.objects.create_user(name, password=password)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(self.venue)
        return user

    def test_bloqueo_tras_cinco_intentos_fallidos(self):
        self._user("garzon", Profile.Role.WAITER)
        for _ in range(5):
            self.client.post("/auth/login/", {"username": "garzon", "password": "incorrecta"})
        response = self.client.post("/auth/login/", {"username": "garzon", "password": "Clave#Segura2026"})
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Demasiados intentos", status_code=429)

    def test_ingreso_correcto_reinicia_el_contador(self):
        self._user("caja", Profile.Role.CASHIER)
        for _ in range(3):
            self.client.post("/auth/login/", {"username": "caja", "password": "incorrecta"})
        response = self.client.post("/auth/login/", {"username": "caja", "password": "Clave#Segura2026"})
        self.assertEqual(response.status_code, 302)

    def test_sazon_limita_consultas_y_largo(self):
        self.client.force_login(self._user("mesero", Profile.Role.WAITER))
        response = self.client.post("/assistant/staff/widget/message/", {"message": "x" * 601})
        self.assertEqual(response.status_code, 400)
        cache.set(f"gi-sazon-{User.objects.get(username='mesero').pk}", 30, 60)
        response = self.client.post("/assistant/staff/widget/message/", {"message": "hola"})
        self.assertEqual(response.status_code, 429)

    def test_cabeceras_de_seguridad(self):
        response = self.client.get("/legal/acerca/")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("Referrer-Policy"), "same-origin")
        self.assertIn("camera=()", response.headers.get("Permissions-Policy", ""))

    def test_advertencia_por_contrasena_de_demostracion(self):
        self._user("admin_demo", Profile.Role.VENUE_ADMIN, password="AdminDemo123!")
        titles = [title for _, title, _ in security_warnings()]
        self.assertTrue(any("admin_demo" in t for t in titles))
