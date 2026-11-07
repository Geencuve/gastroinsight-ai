from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile
from venues.models import Venue


class LayoutTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local de prueba")
        self.admin = User.objects.create_user("jefe", password="Test12345!", is_superuser=True, is_staff=True)
        profile, _ = Profile.objects.get_or_create(user=self.admin)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()

    def test_barra_lateral_con_secciones(self):
        self.client.force_login(self.admin)
        response = self.client.get("/")
        for text in ('class="main-nav app-sidebar"', "side-link", "Mis alertas", "Visión IA", "js/layout.js",
                     "Cerrar sesión", "Ver tour guiado"):
            self.assertContains(response, text)

    def test_supervisor_usa_pestanas_y_cocina_panel_plegable(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/supervisor/"), 'data-tabs="supervisor"')
        self.assertContains(self.client.get("/cocina/"), "fold-card")

    def test_visitante_ve_ingresar_sin_barra_lateral(self):
        response = self.client.get("/legal/acerca/")
        self.assertNotContains(response, "app-sidebar")
        self.assertContains(response, "Ingresar")
