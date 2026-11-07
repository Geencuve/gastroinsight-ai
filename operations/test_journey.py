from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from assistant_chat import services
from authentication.models import Profile
from cameras.models import Camera
from menus.models import Dish, Menu
from operations.models import RestaurantTable, ServiceSession
from sales.models import Order, OrderItem
from venues.models import Venue


class JourneyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.venue = Venue.objects.create(name="Local")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="M1", capacity=4)
        self.dish = Dish.objects.create(menu=Menu.objects.create(venue=self.venue, name="Carta"), name="Lomo",
                                        category="Fondo", price=Decimal("15990"))
        camera = Camera.objects.create(venue=self.venue, name="Cam", source="demo", source_type=Camera.SourceType.DEMO)
        self.analysis = AnalysisSession.objects.create(camera=camera, status="completed")

    def _user(self, name, role):
        user = User.objects.create_user(name, password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(self.venue)
        return user

    def _session(self):
        now = timezone.now()
        start = now - timedelta(minutes=60)
        session = ServiceSession.objects.create(table=self.table, guests_count=2)
        ServiceSession.objects.filter(pk=session.pk).update(status=ServiceSession.Status.CLOSED, started_at=start,
                                                            bill_requested_at=now - timedelta(minutes=10))
        order = Order.objects.create(service_session=session, created_by=self._user(f"m{session.pk}", Profile.Role.WAITER))
        item = OrderItem.objects.create(order=order, dish=self.dish, quantity=1)
        Order.objects.filter(pk=order.pk).update(status=Order.Status.PAID, confirmed_at=start + timedelta(minutes=5),
                                                 paid_at=now - timedelta(minutes=2))
        OrderItem.objects.filter(pk=item.pk).update(delivered_at=start + timedelta(minutes=30))
        for minute, ieo in ((2, 70), (15, 40), (40, 72), (55, 66)):
            event = DetectionEvent.objects.create(session=self.analysis, faces_count=2, table=self.table,
                                                  service_session_id=session.pk, experience_index=Decimal(ieo))
            DetectionEvent.objects.filter(pk=event.pk).update(detected_at=start + timedelta(minutes=minute))
        return session

    def test_journey_del_local_con_punto_de_dolor(self):
        for _ in range(3):
            self._session()
        self.client.force_login(self._user("sup", Profile.Role.SUPERVISOR))
        response = self.client.get("/supervisor/journey/")
        for text in ("Llegada y pedido", "Esperando los platos", "Pago en caja", "<polyline", "Punto de dolor: «Esperando los platos»"):
            self.assertContains(response, text)

    def test_journey_de_una_atencion(self):
        session = self._session()
        self.client.force_login(self._user("sup2", Profile.Role.SUPERVISOR))
        response = self.client.get(f"/supervisor/journey/{session.pk}/")
        self.assertContains(response, "Mesa M1")
        self.assertContains(response, "band-espera")
        self.assertContains(response, "La experiencia bajó en «Esperando los platos»")

    def test_garzon_no_accede_y_sazon_responde(self):
        self._session()
        self.client.force_login(self._user("garzon", Profile.Role.WAITER))
        self.assertEqual(self.client.get("/supervisor/journey/").status_code, 403)
        text, intent, _ = services.build_staff_response(self._user("jefa", Profile.Role.VENUE_ADMIN),
                                                        "¿En qué etapa cae la experiencia?")
        self.assertEqual(intent, "journey")
        self.assertIn("Esperando los platos", text)

    def test_coordenadas_con_punto_decimal(self):
        for _ in range(3):
            self._session()
        self.client.force_login(self._user("sup3", Profile.Role.SUPERVISOR))
        html = self.client.get("/supervisor/journey/").content.decode()
        self.assertRegex(html, r'<rect x="\d+(\.\d+)?" y="262"')
        self.assertNotRegex(html, r'(x|y|cx|cy|width)="-?\d+,\d')
