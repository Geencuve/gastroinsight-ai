from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile
from menus.models import Dish, Menu
from operations.models import RestaurantTable, ServiceSession
from sales.forms import OrderCreateForm
from sales.models import Order
from venues.models import Venue


class OrderFlowTests(TestCase):
    """Flujo completo de la demo: pedido, productos, confirmación, pago y cierre de mesa."""

    def setUp(self):
        self.user = User.objects.create_user(
            "cajero", password="Test12345!", is_staff=True, is_superuser=True,
        )
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()

        venue = Venue.objects.create(name="Local de prueba")
        menu = Menu.objects.create(venue=venue, name="Carta de prueba")
        self.dish = Dish.objects.create(menu=menu, name="Plato de prueba", price=Decimal("8000"))
        table = RestaurantTable.objects.create(venue=venue, code="X1", capacity=4)
        self.session = ServiceSession.objects.create(table=table, guests_count=2, created_by=self.user)
        self.client.force_login(self.user)

    def test_formulario_de_pedido_lista_sesiones_abiertas(self):
        form = OrderCreateForm(user=self.user)
        self.assertIn(self.session, form.fields["service_session"].queryset)

    def test_flujo_completo_pedido_pago_y_cierre(self):
        response = self.client.post("/sales/create/", {"service_session": self.session.id, "notes": ""})
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(service_session=self.session)

        self.client.post(f"/sales/{order.id}/items/add/", {"dish": self.dish.id, "quantity": 2, "notes": ""})
        order.refresh_from_db()
        self.assertEqual(order.subtotal, Decimal("16000"))

        response = self.client.post(f"/sales/{order.id}/confirm/", follow=True)
        html = response.content.decode("utf-8")
        self.assertEqual(html.count(f"Pedido #{order.id} confirmado."), 1, "El mensaje debe aparecer una sola vez")

        self.client.post(f"/sales/{order.id}/pay/", {"payment_method": "CASH"})
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

        response = self.client.get(f"/sales/{order.id}/")
        self.assertContains(response, "Cerrar mesa X1")

        self.client.post(f"/operations/sessions/{self.session.id}/close/")
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, ServiceSession.Status.CLOSED)

    def test_descuento_mayor_al_subtotal_explica_el_motivo(self):
        order = Order.objects.create(service_session=self.session, created_by=self.user)
        self.client.post(f"/sales/{order.id}/items/add/", {"dish": self.dish.id, "quantity": 1, "notes": ""})
        response = self.client.post(f"/sales/{order.id}/discount/", {"discount_amount": "99999"}, follow=True)
        self.assertContains(response, "mayor al subtotal")
