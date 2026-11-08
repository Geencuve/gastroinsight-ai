"""Tutorial de la API: accesible desde Integraciones, con los datos reales del local y solo para gestión."""
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from authentication.models import Profile
from cameras.models import Camera
from operations.models import RestaurantTable
from venues.models import Venue


class ApiTutorialTests(TestCase):
    def setUp(self):
        cache.clear()
        self.venue = Venue.objects.create(name="Local Tutorial")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="T07", capacity=4)
        self.camera = Camera.objects.create(venue=self.venue, name="Cámara patio", source="0", table=self.table)

    def _login(self, role):
        user = User.objects.create_user(f"u_{role}", password="Clave#Segura2026")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(self.venue)
        self.client.force_login(user)

    def test_tutorial_usa_mesas_y_camaras_del_local(self):
        self._login(Profile.Role.VENUE_ADMIN)
        response = self.client.get("/gestion/api/tutorial/")
        self.assertEqual(response.status_code, 200)
        for text in ("data-api-tutorial", "/api/v1/", '"T07"', "Cámara patio", "Invoke-RestMethod", "429"):
            self.assertContains(response, text)
        self.assertContains(response, f'"camara": {self.camera.pk}')

    def test_integraciones_enlaza_el_tutorial(self):
        self._login(Profile.Role.VENUE_ADMIN)
        self.assertContains(self.client.get("/gestion/"), "/gestion/api/tutorial/")

    def test_personal_de_servicio_no_accede(self):
        self._login(Profile.Role.WAITER)
        self.assertNotEqual(self.client.get("/gestion/api/tutorial/").status_code, 200)
