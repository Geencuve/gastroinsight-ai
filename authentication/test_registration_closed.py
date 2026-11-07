from django.contrib.auth.models import User
from django.test import TestCase, override_settings


class ClosedRegistrationTests(TestCase):
    def test_registro_publico_cerrado(self):
        response = self.client.get("/auth/register/")
        self.assertRedirects(response, "/auth/login/", fetch_redirect_response=False)
        before = User.objects.count()
        self.client.post("/auth/register/", {"username": "intruso", "password1": "Clave#Segura2026", "password2": "Clave#Segura2026"})
        self.assertEqual(User.objects.count(), before)

    def test_pantalla_sin_enlace_de_registro(self):
        response = self.client.get("/auth/login/")
        self.assertNotContains(response, "Regístrate aquí")
        self.assertContains(response, "Pídela al administrador de tu local")
        self.assertContains(response, "Pide a tu supervisor que la restablezca")

    @override_settings(ALLOW_SELF_REGISTRATION=True)
    def test_panel_advierte_si_se_reabre(self):
        from core.security_checks import security_warnings

        self.assertTrue(any("registro público" in title for _, title, _ in security_warnings()))
