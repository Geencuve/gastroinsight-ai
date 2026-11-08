"""Datos de demostración: journey completo con lectura en caja y alerta sostenida reproducible."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from ai_vision.services.checkout import checkout_at_payment
from operations.models import AlertSettings, RestaurantTable
from operations.services.journey import journey_stats
from operations.services.sustained import sustained_impatience
from sales.models import Order
from venues.models import Venue


class DemoJourneyTests(TestCase):
    def test_journey_completo_y_lectura_en_caja(self):
        out = StringIO()
        call_command("seed_demo_data", stdout=out)
        call_command("seed_demo_sales", reset=True, stdout=out)
        call_command("seed_demo_journey", reset=True, stdout=out)
        venue = Venue.objects.get(name="Restaurante Demo Santiago")
        stats = journey_stats([venue])
        self.assertTrue(all(s["ieo"] is not None for s in stats), stats)
        order = Order.objects.filter(paid_at__isnull=False, service_session__notes="Generado automáticamente para demo.").order_by("-paid_at").first()
        self.assertIsNotNone(checkout_at_payment(order))


class DemoAlertaTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local Alerta")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="M04", capacity=4)

    def test_ejemplo_de_la_docente_13_alerta_y_10_no(self):
        args = {"mesa": "M04", "umbral": 80, "sostenido": 12, "sin_seguir": True, "stdout": StringIO()}
        call_command("demo_alerta_sostenida", minutos=13, **args)
        cfg = AlertSettings.objects.get(venue=self.venue)
        self.assertTrue(sustained_impatience(self.table, cfg))
        call_command("demo_alerta_sostenida", minutos=10, **args)
        self.assertFalse(sustained_impatience(self.table, cfg))
        call_command("demo_alerta_sostenida", limpiar=True, stdout=StringIO())