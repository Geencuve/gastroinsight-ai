from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from cameras.models import Camera
from operations.models import RestaurantTable
from privacy.models import PrivacyPolicy
from venues.models import Venue


@override_settings(DESKTOP_MODE=True)
class FirstRunTests(TestCase):
    def test_sin_administrador_redirige_al_asistente(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/primer-uso/", fetch_redirect_response=False)

    def test_asistente_configura_el_local(self):
        response = self.client.post("/primer-uso/", {
            "venue_name": "Burger Express", "address": "Av. Siempre Viva 123", "tables": 5,
            "first_name": "Carla", "username": "carla", "password1": "Hamburguesa#2026", "password2": "Hamburguesa#2026",
        })
        self.assertRedirects(response, "/?tour=1", fetch_redirect_response=False)
        user = User.objects.get(username="carla")
        self.assertTrue(user.is_superuser)
        venue = Venue.objects.get(name="Burger Express")
        self.assertEqual(RestaurantTable.objects.filter(venue=venue).count(), 5)
        self.assertTrue(Camera.objects.filter(venue=venue, table__code="M01").exists())
        self.assertTrue(PrivacyPolicy.objects.filter(venue=venue, processing_enabled=True).exists())
        self.assertRedirects(self.client.get("/primer-uso/"), "/", fetch_redirect_response=False)

    def test_contrasenas_distintas_son_rechazadas(self):
        response = self.client.post("/primer-uso/", {
            "venue_name": "Local", "tables": 2, "first_name": "Ana", "username": "ana",
            "password1": "Hamburguesa#2026", "password2": "Otra#2026",
        })
        self.assertContains(response, "no coinciden")
        self.assertFalse(User.objects.exists())
