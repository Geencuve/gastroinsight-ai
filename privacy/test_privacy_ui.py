"""Privacidad v2: marco legal visible, lista de cumplimiento e imágenes bloqueadas."""
from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile
from privacy.models import PrivacyPolicy
from venues.models import Venue


class PrivacyUiTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local Privado")
        user = User.objects.create_user("jefa", password="Clave#Segura2026", is_superuser=True, is_staff=True)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.client.force_login(user)

    def test_listado_explica_ley_y_cumplimiento(self):
        response = self.client.get("/privacy/")
        for text in ("Ley N° 19.628", "Ley N° 21.719", "Licitud y finalidad", "Estado por local", "Autorización vigente registrada"):
            self.assertContains(response, text)

    def test_formulario_por_secciones_e_imagenes_bloqueadas(self):
        response = self.client.get(f"/privacy/policy/{self.venue.id}/")
        self.assertContains(response, "Para qué se procesa")
        self.assertContains(response, 'id="dlg-auth"')
        self.client.post(f"/privacy/policy/{self.venue.id}/", {
            "version": "1.1", "purpose": "Medir ocupación y experiencia por mesa sin identificar personas.",
            "retain_aggregated_events_days": 30, "retain_incidents_days": 90, "store_original_images": "on"})
        policy = PrivacyPolicy.objects.get(venue=self.venue)
        self.assertEqual(policy.version, "1.1")
        self.assertFalse(policy.store_original_images)
    def test_leyes_enlazan_texto_oficial(self):
        response = self.client.get("/privacy/")
        self.assertContains(response, "https://www.bcn.cl/leychile/navegar?idLey=19628")
        self.assertContains(response, "https://www.bcn.cl/leychile/navegar?idLey=21719")
        self.assertContains(self.client.get(f"/privacy/policy/{self.venue.id}/"), "idLey=19628")
