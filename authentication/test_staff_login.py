from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile


class StaffLoginTests(TestCase):
    def _user(self, name, role):
        user = User.objects.create_user(name, password="Clave#Segura2026")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        return user

    def test_acceso_del_personal_rechaza_cuentas_de_gestion(self):
        for role in (Profile.Role.SUPERVISOR, Profile.Role.VENUE_ADMIN, Profile.Role.PLATFORM_ADMIN):
            self._user(f"u_{role}", role)
            response = self.client.post("/auth/login/", {"username": f"u_{role}", "password": "Clave#Segura2026"})
            self.assertContains(response, "Ingresa por el Acceso de gestión")
            self.assertNotIn("_auth_user_id", self.client.session)

    def test_acceso_del_personal_admite_al_garzon(self):
        self._user("garzon", Profile.Role.WAITER)
        response = self.client.post("/auth/login/", {"username": "garzon", "password": "Clave#Segura2026"})
        self.assertEqual(response.status_code, 302)

    def test_paginas_se_pueden_incrustar_solo_en_la_misma_aplicacion(self):
        response = self.client.get("/legal/acerca/")
        self.assertEqual(response.headers.get("X-Frame-Options"), "SAMEORIGIN")
