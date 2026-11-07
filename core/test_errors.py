from django.contrib.auth.models import User
from django.test import Client, TestCase

from authentication.models import Profile


class FriendlyErrorTests(TestCase):
    def test_formulario_vencido_sin_sesion_vuelve_al_login(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post("/auth/login/", {"username": "x", "password": "y"})
        self.assertRedirects(response, "/auth/login/", fetch_redirect_response=False)

    def test_formulario_vencido_con_sesion_va_al_inicio(self):
        user = User.objects.create_user("ana", password="Test12345!")
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        response = client.post("/auth/login/", {"username": "ana", "password": "Test12345!"})
        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_acceso_denegado_con_pagina_amigable(self):
        user = User.objects.create_user("sinlocal", password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.OPERATOR
        profile.save()
        self.client.force_login(user)
        response = self.client.get("/assistant/staff/")
        self.assertContains(response, "Acceso restringido", status_code=403)
        self.assertContains(response, "No tienes locales activos asignados", status_code=403)
