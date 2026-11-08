from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile
from operations.models import RestaurantTable
from sales.models import Order
from venues.models import Venue


class OperationalRolesTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="M1", capacity=4)

    def _login(self, name, role):
        user = User.objects.create_user(name, password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(self.venue)
        self.client.force_login(user)
        return user

    def test_garzon_caja_y_supervisor_operan_pedidos_y_atenciones(self):
        for role in (Profile.Role.WAITER, Profile.Role.CASHIER, Profile.Role.SUPERVISOR):
            self._login(f"u_{role}", role)
            for path in ("/sales/create/", "/operations/sessions/create/", "/operations/evaluations/create/"):
                self.assertEqual(self.client.get(path).status_code, 200, f"{role} en {path}")

    def test_garzon_llega_al_punto_de_venta_y_puede_verlo(self):
        self._login("garzon", Profile.Role.WAITER)
        response = self.client.post(f"/sala/mesa/{self.table.id}/abrir/", {"guests": "2"}, follow=True)
        self.assertEqual(response.status_code, 200)
        order = Order.objects.get(service_session__table=self.table)
        self.assertEqual(self.client.get(f"/sales/{order.id}/").status_code, 200)

    def test_visualizador_cocina_y_barra_siguen_sin_operar_pedidos(self):
        for role in (Profile.Role.VIEWER, Profile.Role.KITCHEN, Profile.Role.BAR):
            self._login(f"v_{role}", role)
            self.assertEqual(self.client.get("/sales/create/").status_code, 403, role)
