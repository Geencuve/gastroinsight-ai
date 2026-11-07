from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from authentication.models import Profile
from menus.models import Dish, Menu
from operations.models import RestaurantTable, ServiceSession
from operations.views_floor import session_token
from sales.models import Order, OrderItem
from sales.services.kitchen import queue
from venues.models import Venue


class ReceiptAndFeedbackTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local de prueba", address="Av. Siempre Viva 123")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="M1", capacity=4)
        self.user = User.objects.create_user("jefa", password="Test12345!", is_superuser=True, is_staff=True)
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.session = ServiceSession.objects.create(table=self.table, guests_count=2, created_by=self.user)
        menu = Menu.objects.create(venue=self.venue, name="Carta")
        self.dish = Dish.objects.create(menu=menu, name="Lomo vetado", category="Fondo", price=Decimal("15990"))
        self.order = Order.objects.create(service_session=self.session, created_by=self.user)
        OrderItem.objects.create(order=self.order, dish=self.dish, quantity=2)

    def _pay(self):
        Order.objects.filter(pk=self.order.pk).update(status=Order.Status.PAID, paid_at=timezone.now())

    def test_evaluacion_se_habilita_solo_tras_el_pago(self):
        url = f"/opinion/atencion/{session_token(self.session)}/"
        self.assertContains(self.client.get(url), "se habilita al pagar")
        self._pay()
        self.assertContains(self.client.get(url), "precio-calidad")

    def test_qr_por_mesa_lleva_a_la_evaluacion_solo_si_pagaron(self):
        with mock.patch("operations.feedback.table_from_token", return_value=self.table):
            self.assertContains(self.client.get("/opinion/cualquiera/"), "se habilita al pagar")
            self._pay()
            response = self.client.get("/opinion/cualquiera/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/opinion/atencion/", response["Location"])

    def test_codigo_por_mesa_alterado_es_rechazado(self):
        self.assertEqual(self.client.get(f"/opinion/{self.table.id}:firmafalsa/").status_code, 404)

    def test_boleta_con_detalle_total_y_qr(self):
        self.client.force_login(self.user)
        response = self.client.get(f"/caja/boleta/{self.order.id}/")
        self.assertRedirects(response, "/caja/", fetch_redirect_response=False)
        self._pay()
        response = self.client.get(f"/caja/boleta/{self.order.id}/")
        for text in ("Lomo vetado", "Total", "¿Cómo estuvo tu visita?", "<svg", "boleta electrónica del SII"):
            self.assertContains(response, text)
        self.assertContains(self.client.get("/caja/"), "Pagados en la última hora")

    def test_platos_agregados_despues_de_confirmar_van_aparte(self):
        OrderItem.objects.filter(order=self.order).update(created_at=timezone.now() - timedelta(minutes=11))
        Order.objects.filter(pk=self.order.pk).update(status=Order.Status.CONFIRMED,
                                                      confirmed_at=timezone.now() - timedelta(minutes=10))
        pure = Dish.objects.create(menu=self.dish.menu, name="Puré rústico", category="Acompañamiento", price=Decimal("3990"))
        extra = OrderItem.objects.create(order=self.order, dish=pure, quantity=1)
        pending = queue(Venue.objects.all(), "cocina")["columns"][0]["cards"]
        self.assertEqual(len(pending), 2)
        addon = next(card for card in pending if card["addon"])
        self.assertEqual(addon["ids"], [extra.id])

    def test_pagina_de_codigos_qr_por_mesa(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/opinion/qr/").status_code, 200)
