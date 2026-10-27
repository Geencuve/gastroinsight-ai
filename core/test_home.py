from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile


class HomeTests(TestCase):
    def test_visitante_ve_presentacion_e_ingresar(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no biométrica")
        self.assertContains(response, "Ingresar")
        self.assertNotContains(response, "análisis de emociones")

    def test_usuario_ve_indicadores_y_secciones_de_negocio(self):
        user = User.objects.create_user("gerente", password="Test12345!", is_superuser=True, is_staff=True)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.client.force_login(user)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        for text in ("Vendido hoy", "Oportunidades de venta", "Ideas de marketing", "Mejoras en la experiencia"):
            self.assertContains(response, text)
