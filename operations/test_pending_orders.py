from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Profile
from menus.models import Dish, Menu
from operations.models import RestaurantTable, ServiceSession
from sales.models import Order, OrderItem
from venues.models import Venue


class PendingOrdersTests(TestCase):
    """Una mesa no puede cerrarse ni cancelarse con pedidos sin pagar."""

    def setUp(self):
        self.user = User.objects.create_user(
            "tester", password="Test12345!", is_staff=True, is_superuser=True,
        )
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()

        venue = Venue.objects.create(name="Local de prueba")
        menu = Menu.objects.create(venue=venue, name="Carta de prueba")
        self.dish = Dish.objects.create(menu=menu, name="Plato de prueba", price=Decimal("10000"))
        self.table = RestaurantTable.objects.create(venue=venue, code="X1", capacity=4)
        self.session = ServiceSession.objects.create(
            table=self.table, guests_count=2, created_by=self.user,
        )
        self.order = Order.objects.create(service_session=self.session, created_by=self.user)
        OrderItem.objects.create(order=self.order, dish=self.dish, quantity=2)
        self.client.force_login(self.user)

    def test_cerrar_mesa_con_pedido_abierto_es_rechazado(self):
        with self.assertRaises(ValidationError):
            self.session.close(self.user)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, ServiceSession.Status.OPEN)

    def test_cancelar_mesa_con_pedido_confirmado_es_rechazado(self):
        self.order.confirm()
        with self.assertRaises(ValidationError):
            self.session.cancel(self.user)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, ServiceSession.Status.OPEN)

    def test_cerrar_mesa_despues_de_pagar_es_permitido(self):
        self.order.confirm()
        self.order.mark_as_paid(Order.PaymentMethod.CASH)
        self.assertTrue(self.session.close(self.user))

    def test_cerrar_mesa_despues_de_anular_pedido_es_permitido(self):
        self.order.cancel()
        self.assertTrue(self.session.close(self.user))

    def test_vista_cerrar_muestra_mensaje_y_no_cierra(self):
        response = self.client.post(
            f"/operations/sessions/{self.session.id}/close/", follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "anúlalos")
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, ServiceSession.Status.OPEN)

    def test_lista_de_sesiones_indica_pedidos_sin_pagar(self):
        response = self.client.get("/operations/sessions/")
        self.assertContains(response, "pedido sin pagar")

    def test_descuento_en_mesa_cerrada_no_genera_error_500(self):
        ServiceSession.objects.filter(pk=self.session.pk).update(
            status=ServiceSession.Status.CLOSED,
        )
        response = self.client.post(
            f"/sales/{self.order.id}/discount/", {"discount_amount": "1000"},
        )
        self.assertNotEqual(response.status_code, 500)
