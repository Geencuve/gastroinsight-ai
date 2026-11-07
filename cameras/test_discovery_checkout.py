from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from ai_vision.services.checkout import checkout_at_payment, live_checkout
from ai_vision.services.discovery import validate_url
from authentication.models import Profile
from cameras.models import Camera
from operations.models import Notification, RestaurantTable, ServiceSession
from operations.services.notifications import generate
from sales.models import Order
from venues.models import Venue


class CameraDiscoveryAndCheckoutTests(TestCase):
    def setUp(self):
        cache.clear()
        self.venue = Venue.objects.create(name="Local")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="M1", capacity=4)

    def _user(self, name, role):
        user = User.objects.create_user(name, password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(self.venue)
        return user

    def _checkout_event(self, ieo, seconds_ago=10):
        camera, _ = Camera.objects.get_or_create(venue=self.venue, name="Caja", source="1",
                                                 defaults={"source_type": Camera.SourceType.WEBCAM, "is_checkout": True})
        analysis = AnalysisSession.objects.create(camera=camera, status="running")
        event = DetectionEvent.objects.create(session=analysis, faces_count=1, experience_index=Decimal(ieo),
                                              valence=Decimal("-0.3"), attention_seeking=Decimal("0.2"))
        DetectionEvent.objects.filter(pk=event.pk).update(detected_at=timezone.now() - timedelta(seconds=seconds_ago))

    @mock.patch("ai_vision.services.discovery.probe_local",
                return_value=[{"source": "0", "label": "Cámara local #0 (integrada)", "resolution": "1280×720", "working": True}])
    def test_detectar_y_asignar_camara_de_caja(self, _probe):
        self.client.force_login(self._user("jefa", Profile.Role.VENUE_ADMIN))
        self.assertContains(self.client.get("/gestion/camaras/detectar/?buscar=1"), "Cámara local #0")
        self.client.post("/gestion/camaras/detectar/", {"accion": "registrar", "source": "0", "name": "Caja principal",
                                                        "venue": self.venue.id, "uso": "caja"})
        camera = Camera.objects.get(name="Caja principal")
        self.assertTrue(camera.is_checkout)
        self.assertIsNone(camera.table)
        self.assertContains(self.client.get("/gestion/camaras/detectar/?buscar=1"), "Ya registrada")

    def test_asignar_camara_de_mesa_exige_mesa(self):
        self.client.force_login(self._user("jefe", Profile.Role.VENUE_ADMIN))
        self.client.post("/gestion/camaras/detectar/", {"accion": "registrar", "source": "2", "venue": self.venue.id, "uso": "mesa"})
        self.assertFalse(Camera.objects.filter(source="2").exists())
        self.client.post("/gestion/camaras/detectar/", {"accion": "registrar", "source": "2", "venue": self.venue.id,
                                                        "uso": "mesa", "table": self.table.id})
        self.assertEqual(Camera.objects.get(source="2").table, self.table)

    def test_solo_acepta_direcciones_de_camaras_de_red(self):
        for bad in ("file:///C:/Windows/win.ini", "C:\\\\datos\\\\video.mp4", "ftp://servidor/cam"):
            with self.assertRaises(ValueError):
                validate_url(bad)
        self.assertEqual(validate_url("rtsp://192.168.1.50:554/stream1"), "rtsp://192.168.1.50:554/stream1")

    def test_cliente_en_caja_y_experiencia_al_pagar(self):
        self._checkout_event("72")
        self.assertEqual(live_checkout([self.venue])["ieo"], 72)
        session = ServiceSession.objects.create(table=self.table, guests_count=2)
        order = Order.objects.create(service_session=session, created_by=self._user("mozo", Profile.Role.WAITER))
        Order.objects.filter(pk=order.pk).update(status=Order.Status.PAID, paid_at=timezone.now())
        order.refresh_from_db()
        self.assertEqual(checkout_at_payment(order)["ieo"], 72)
        self.client.force_login(self._user("cajera", Profile.Role.CASHIER))
        response = self.client.get("/caja/")
        self.assertContains(response, "Cliente en caja ahora")
        self.assertContains(response, "IEO en caja al pagar: 72")

    def test_alerta_a_caja_por_disconformidad(self):
        self._checkout_event("38")
        generate(Venue.objects.all())
        self.assertTrue(Notification.objects.filter(kind="checkout").exists())
        self.client.force_login(self._user("caja", Profile.Role.CASHIER))
        cache.clear()
        kinds = [item["kind"] for item in self.client.get("/notificaciones/").json()["items"]]
        self.assertIn("checkout", kinds)
