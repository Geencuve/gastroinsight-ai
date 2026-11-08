"""Mi perfil v2: secciones plegables con resumen y cambio de contraseña con el mismo estilo."""
from django.contrib.auth.models import User
from django.test import TestCase


class ProfileUiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("persona", password="Clave#Segura2026", email="p@local.cl")
        self.client.force_login(self.user)

    def test_perfil_con_secciones_plegables(self):
        response = self.client.get("/auth/profile/")
        self.assertEqual(response.content.decode().count("data-prof>"), 5)
        for text in ('id="configuracion"', "Abrir todo", "p@local.cl"):
            self.assertContains(response, text)

    def test_cambiar_contrasena_con_estilo(self):
        response = self.client.get("/auth/password/change/")
        self.assertContains(response, "data-pass-toggle")
        self.assertContains(response, "#seguridad")