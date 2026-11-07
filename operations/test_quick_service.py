from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile
from operations.models import RestaurantTable, ServiceSession
from sales.models import Order
from venues.models import Venue


class QuickServiceTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="M1", capacity=4)
        self.waiter = User.objects.create_user("garzon", password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=self.waiter)
        profile.role = Profile.Role.WAITER
        profile.save()
        profile.venues.add(self.venue)
        self.client.force_login(self.waiter)

    def test_salon_ofrece_abrir_mesa_libre(self):
        response = self.client.get("/sala/")
        self.assertContains(response, f"/sala/mesa/{self.table.id}/abrir/")
        self.assertContains(response, "Abrir mesa")

    def test_abrir_mesa_lleva_directo_al_punto_de_venta(self):
        response = self.client.post(f"/sala/mesa/{self.table.id}/abrir/", {"guests": "3"}, follow=True)
        session = ServiceSession.objects.get(table=self.table, status=ServiceSession.Status.OPEN)
        self.assertEqual(session.guests_count, 3)
        order = Order.objects.get(service_session=session)
        self.assertEqual(response.redirect_chain[-1][0], f"/sales/{order.id}/")

    def test_pedido_abierto_se_retoma_sin_duplicar(self):
        self.client.post(f"/sala/mesa/{self.table.id}/abrir/", {"guests": "2"})
        self.client.get(f"/sala/mesa/{self.table.id}/pedido/")
        self.client.get(f"/sala/mesa/{self.table.id}/pedido/")
        self.assertEqual(Order.objects.filter(service_session__table=self.table).count(), 1)

    def test_mesa_sin_atencion_no_crea_pedido(self):
        response = self.client.get(f"/sala/mesa/{self.table.id}/pedido/")
        self.assertRedirects(response, "/sala/", fetch_redirect_response=False)
        self.assertFalse(Order.objects.exists())
