"""Evaluaciones: la pantalla carga el script de filtros y grupos por día."""
from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile


class EvaluationsUiTests(TestCase):
    def test_pantalla_carga_filtros(self):
        user = User.objects.create_user("jefa", password="Clave#Segura2026", is_superuser=True, is_staff=True)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.client.force_login(user)
        response = self.client.get("/operations/evaluations/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/evaluations.js")