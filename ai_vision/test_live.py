from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from ai_vision.services.live import build_live_state
from analytics.services.correlation import build_dataset
from assistant_chat.services import build_staff_response
from authentication.models import Profile
from cameras.models import Camera
from operations.models import RestaurantTable, ServiceSession
from venues.models import Venue


class LiveMonitorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("monitor", password="Test12345!", is_staff=True, is_superuser=True)
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.venue = Venue.objects.create(name="Local de prueba")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="X1", capacity=4)
        self.camera = Camera.objects.create(venue=self.venue, name="Cam demo", source="demo",
                                            source_type=Camera.SourceType.DEMO, table=self.table)
        self.service = ServiceSession.objects.create(table=self.table, guests_count=2)
        self.analysis = AnalysisSession.objects.create(camera=self.camera, status="running")

    def _event(self, seconds_ago, attention, index):
        DetectionEvent.objects.create(
            session=self.analysis, detected_at=timezone.now() - timedelta(seconds=seconds_ago), faces_count=2,
            table=self.table, service_session=self.service, occupancy=Decimal("2"),
            attention_seeking=Decimal(str(attention)), experience_index=Decimal(str(index)), valence=Decimal("0.1"),
        )

    def test_alerta_por_clientes_buscando_atencion(self):
        self._event(20, 0.5, 60)
        state = build_live_state(Venue.objects.all())
        card = state["cards"][0]
        self.assertTrue(card["live"])
        self.assertEqual(card["level"], "alerta")
        self.assertIn("Clientes buscando atención", card["reasons"])

    def test_endpoint_del_monitor(self):
        self._event(10, 0.05, 72)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/ai/monitor/").status_code, 200)
        data = self.client.get("/ai/monitor/data/").json()
        self.assertEqual(data["summary"]["live_tables"], 1)
        self.assertEqual(data["cards"][0]["ieo"], 72.0)

    def test_simulador_genera_lecturas_y_cierra_sesiones(self):
        call_command("simulate_live", ticks=2, interval=0)
        self.assertEqual(DetectionEvent.objects.filter(session__error_message__icontains="Simulación").count(), 2)
        self.assertFalse(AnalysisSession.objects.filter(status="running", error_message__icontains="Simulación").exists())

    def test_asistente_responde_estado_en_vivo(self):
        self._event(15, 0.05, 70)
        text, intent, _ = build_staff_response(self.user, "¿Cómo están las mesas ahora?")
        self.assertEqual(intent, "live_status")
        self.assertIn("Mesa X1", text)

    def test_dataset_de_correlacion_incluye_ieo(self):
        start = timezone.now() - timedelta(hours=3)
        ServiceSession.objects.filter(pk=self.service.pk).update(status="closed", started_at=start, ended_at=start + timedelta(minutes=50))
        self._event(3 * 3600 - 600, 0.1, 64)
        for _ in range(3):
            DetectionEvent.objects.create(session=self.analysis, faces_count=2, table=self.table, service_session=self.service,
                                          emotion_distribution={"happy": 5, "neutral": 5}, experience_index=Decimal("64"))
        today = timezone.localdate()
        rows = build_dataset(Venue.objects.all(), today - timedelta(days=1), today)
        self.assertEqual(rows[0]["ieo"], 64.0)
