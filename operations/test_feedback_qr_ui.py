"""Códigos QR: la pantalla trae selección e impresión propia con cada mesa."""
from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile
from operations.models import RestaurantTable
from venues.models import Venue


class FeedbackQrUiTests(TestCase):
    def test_pantalla_qr_con_seleccion_e_impresion(self):
        venue = Venue.objects.create(name="Local QR")
        RestaurantTable.objects.create(venue=venue, code="Q01", capacity=4, zone_name="Terraza")
        user = User.objects.create_user("jefa", password="Clave#Segura2026", is_superuser=True, is_staff=True)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.client.force_login(user)
        response = self.client.get("/opinion/qr/")
        self.assertEqual(response.status_code, 200)
        for text in ("data-qr-print", "data-qr-go", "Mesa Q01", "<svg", "@page { size: A4"):
            self.assertContains(response, text)