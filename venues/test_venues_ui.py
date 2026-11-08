"""Locales v2: crear, editar, ficha con toda la configuración y permisos."""
from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile
from venues.models import Venue


class VenuesUiTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local Uno", address="Av. Siempre Viva 123")
        self.admin = self._user("plataforma", Profile.Role.PLATFORM_ADMIN, superuser=True)

    def _user(self, name, role, superuser=False):
        user = User.objects.create_user(name, password="Clave#Segura2026", is_superuser=superuser, is_staff=superuser)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(self.venue)
        return user

    def test_crear_local_lleva_a_su_ficha_y_no_duplica(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/venues/"), 'id="dlg-venue"')
        response = self.client.post("/venues/nuevo/", {"name": "Local Dos", "address": "Providencia"})
        venue = Venue.objects.get(name="Local Dos")
        self.assertRedirects(response, f"/venues/{venue.id}/", fetch_redirect_response=False)
        self.client.post("/venues/nuevo/", {"name": "local dos"})
        self.assertEqual(Venue.objects.filter(name__iexact="local dos").count(), 1)

    def test_ficha_reune_la_configuracion(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/venues/{self.venue.id}/")
        for text in ("Primeros pasos", "Configuración del local", f"/privacy/policy/{self.venue.id}/", "/gestion/", "data-goto-tab", "Desactivar local"):
            self.assertContains(response, text)

    def test_admin_de_local_edita_pero_no_crea_ni_desactiva(self):
        self.client.force_login(self._user("jefe", Profile.Role.VENUE_ADMIN))
        self.client.post(f"/venues/{self.venue.id}/editar/", {"name": "Local Uno Centro", "address": "Centro"})
        self.venue.refresh_from_db()
        self.assertEqual(self.venue.name, "Local Uno Centro")
        self.assertEqual(self.client.post("/venues/nuevo/", {"name": "Otro"}).status_code, 403)
        self.assertEqual(self.client.post(f"/venues/{self.venue.id}/estado/").status_code, 403)

    def test_desactivar_y_reactivar(self):
        self.client.force_login(self.admin)
        self.client.post(f"/venues/{self.venue.id}/estado/")
        self.venue.refresh_from_db()
        self.assertFalse(self.venue.is_active)
        self.assertContains(self.client.get("/venues/"), "Locales inactivos")
        self.client.post(f"/venues/{self.venue.id}/estado/")
        self.venue.refresh_from_db()
        self.assertTrue(self.venue.is_active)