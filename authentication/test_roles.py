from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile
from venues.models import Venue


class RoleScopeTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local de prueba")

    def _login(self, role):
        user = User.objects.create_user(f"u_{role}", password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(self.venue)
        self.client.force_login(user)
        return user

    def test_mesero_opera_pedidos_pero_no_ve_analitica(self):
        self._login(Profile.Role.WAITER)
        self.assertNotEqual(self.client.get("/sales/").status_code, 403)
        response = self.client.get("/analytics/")
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Tu rol no tiene acceso", status_code=403)

    def test_cocina_no_accede_a_ventas_ni_a_camaras(self):
        self._login(Profile.Role.KITCHEN)
        self.assertEqual(self.client.get("/sales/").status_code, 403)
        self.assertEqual(self.client.get("/ai/monitor/").status_code, 403)
        self.assertEqual(self.client.get("/auth/profile/").status_code, 200)

    def test_supervisor_accede_a_analitica_y_monitor(self):
        self._login(Profile.Role.SUPERVISOR)
        self.assertNotEqual(self.client.get("/analytics/").status_code, 403)
        self.assertNotEqual(self.client.get("/ai/monitor/").status_code, 403)
        self.assertEqual(self.client.get("/monitoring/audit/").status_code, 403)

    def test_operador_mantiene_sus_permisos(self):
        self._login(Profile.Role.OPERATOR)
        self.assertNotEqual(self.client.get("/analytics/").status_code, 403)

    def test_menu_recibe_el_alcance_del_rol(self):
        self._login(Profile.Role.CASHIER)
        response = self.client.get("/auth/profile/")
        self.assertContains(response, 'id="gi-role-scope"')
        capabilities = {c["label"]: c["allowed"] for c in response.context["capabilities"]}
        self.assertTrue(capabilities["Caja: cobros y termómetro de la mesa"])
        self.assertFalse(capabilities["Pantalla de cocina (comandas)"])
