from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from cameras.models import Camera
from menus.models import Dish, Menu
from operations.models import RestaurantTable, ServiceSession, WaitlistEntry
from operations.services.journey import journey_stats
from operations.services.vision_insights import vision_insights
from sales.models import Order, OrderItem
from venues.models import Venue


class VisionInsightsTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local")
        self.user = User.objects.create_user("jefa", password="Test12345!")
        self.tables = [RestaurantTable.objects.create(venue=self.venue, code=f"M{i}", capacity=4) for i in range(1, 4)]
        menu = Menu.objects.create(venue=self.venue, name="Carta")
        self.dish = Dish.objects.create(menu=menu, name="Lomo vetado", category="Fondo", price=Decimal("15990"))
        camera = Camera.objects.create(venue=self.venue, name="Cam", source="demo", source_type=Camera.SourceType.DEMO)
        self.analysis = AnalysisSession.objects.create(camera=camera, status="completed")

    def _closed_session(self, table, **fields):
        """Atención histórica: se crea y se cierra (una mesa solo puede tener una atención abierta)."""
        session = ServiceSession.objects.create(table=table, guests_count=2)
        ServiceSession.objects.filter(pk=session.pk).update(status=ServiceSession.Status.CLOSED, **fields)
        session.refresh_from_db()
        return session

    def _session_with_stages(self, table):
        now = timezone.now()
        start = now - timedelta(minutes=60)
        session = self._closed_session(table, started_at=start, bill_requested_at=now - timedelta(minutes=10))
        order = Order.objects.create(service_session=session, created_by=self.user)
        item = OrderItem.objects.create(order=order, dish=self.dish, quantity=1)
        Order.objects.filter(pk=order.pk).update(status=Order.Status.PAID, confirmed_at=start + timedelta(minutes=5),
                                                 paid_at=now - timedelta(minutes=2))
        OrderItem.objects.filter(pk=item.pk).update(delivered_at=start + timedelta(minutes=30))
        for minute, ieo in ((2, 70), (15, 40), (20, 42), (40, 72), (55, 66)):
            event = DetectionEvent.objects.create(session=self.analysis, faces_count=2, table=table,
                                                  service_session=session, experience_index=Decimal(ieo))
            DetectionEvent.objects.filter(pk=event.pk).update(detected_at=start + timedelta(minutes=minute))
        return session

    def test_experiencia_por_etapa_detecta_la_espera_de_platos(self):
        for _ in range(5):
            self._session_with_stages(self.tables[0])
        stages = {s["key"]: s for s in journey_stats(Venue.objects.all())}
        self.assertEqual(stages["espera"]["n"], 5)
        self.assertLess(stages["espera"]["ieo"], stages["consumo"]["ieo"])
        titles = [i["title"] for i in vision_insights(Venue.objects.all())["servicio"]]
        self.assertIn("La experiencia cae en la etapa «Esperando los platos»", titles)

    def test_abandonos_de_lista_de_espera(self):
        for i in range(8):
            WaitlistEntry.objects.create(venue=self.venue, guests=2, cancelled=i < 3)
        titles = [i["title"] for i in vision_insights(Venue.objects.all())["servicio"]]
        self.assertTrue(any("se va sin sentarse" in t for t in titles))

    def test_mesas_poco_usadas(self):
        for table, count in ((self.tables[0], 10), (self.tables[1], 10), (self.tables[2], 1)):
            for _ in range(count):
                self._closed_session(table)
        titles = [i["title"] for i in vision_insights(Venue.objects.all())["servicio"]]
        self.assertIn("Mesas que se usan poco: M3", titles)

    def test_el_inicio_incluye_las_ideas_con_su_metodo(self):
        from core.services.insights import build_insights

        for i in range(8):
            WaitlistEntry.objects.create(venue=self.venue, guests=2, cancelled=i < 3)
        item = next(i for i in build_insights(Venue.objects.all())["servicio"] if "sin sentarse" in i["title"])
        self.assertEqual(item["method"]["name"], "Tasa de abandono de la lista de espera")
