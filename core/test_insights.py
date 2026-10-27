from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from core.services.insights import build_home_summary, build_insights
from core.templatetags.gi_format import clp
from operations.models import RestaurantTable, ServiceSession
from sales.models import Order
from venues.models import Venue


class InsightsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("cajero", password="Test12345!")
        self.venue = Venue.objects.create(name="Local de prueba")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="X1", capacity=4)

    def _paid_order(self, days_ago, total):
        moment = timezone.now() - timedelta(days=days_ago)
        session = ServiceSession.objects.create(
            table=self.table, started_at=moment, guests_count=2, status=ServiceSession.Status.CLOSED,
        )
        ServiceSession.objects.filter(pk=session.pk).update(ended_at=moment + timedelta(minutes=60))
        order = Order.objects.create(service_session=session, created_by=self.user)
        Order.objects.filter(pk=order.pk).update(
            status=Order.Status.PAID, subtotal=total, total=total, paid_at=moment,
        )

    def test_sin_datos_no_genera_sugerencias(self):
        insights = build_insights(Venue.objects.all())
        for key in ("now", "ventas", "marketing", "servicio"):
            self.assertEqual(insights[key], [])

    def test_detecta_caida_de_ventas_como_oportunidad(self):
        for days in (8, 9, 10):
            self._paid_order(days, 50000)
        self._paid_order(1, 20000)
        insights = build_insights(Venue.objects.all())
        self.assertTrue(any("menos que la anterior" in i["title"] for i in insights["ventas"]))

    def test_mesa_abierta_mucho_tiempo_va_a_atender_ahora(self):
        ServiceSession.objects.create(
            table=self.table, started_at=timezone.now() - timedelta(hours=3), guests_count=2,
        )
        insights = build_insights(Venue.objects.all())
        self.assertIn("X1", insights["now"][0]["title"])

    def test_resumen_del_dia_y_ticket_promedio(self):
        self._paid_order(0, 30000)
        summary = build_home_summary(Venue.objects.all())
        self.assertEqual(summary["orders_today"], 1)
        self.assertEqual(int(summary["average_ticket"]), 30000)

    def test_formato_pesos_chilenos(self):
        self.assertEqual(clp(162281), "$162.281")
        self.assertEqual(clp(None), "$0")
