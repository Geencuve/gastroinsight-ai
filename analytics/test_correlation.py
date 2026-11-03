from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from analytics.services.correlation import build_dataset, correlate
from authentication.models import Profile
from cameras.models import Camera
from operations.models import RestaurantTable, ServiceSession
from venues.models import Venue


class CorrelationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("investigador", password="Test12345!", is_staff=True, is_superuser=True)
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.venue = Venue.objects.create(name="Local de prueba")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="X1", capacity=4)
        self.camera = Camera.objects.create(
            venue=self.venue, name="Cam demo", source="demo",
            source_type=Camera.SourceType.DEMO, table=self.table,
        )

    def _session_with_events(self, minutes, distribution):
        start = timezone.now() - timedelta(hours=5)
        service = ServiceSession.objects.create(table=self.table, started_at=start, guests_count=2, status="closed")
        ServiceSession.objects.filter(pk=service.pk).update(ended_at=start + timedelta(minutes=minutes))
        analysis = AnalysisSession.objects.create(camera=self.camera, status="completed")
        DetectionEvent.objects.create(
            session=analysis, faces_count=2, emotion_distribution=distribution,
            table=self.table, service_session=service,
        )
        return service

    def test_correlacion_lineal_perfecta_es_significativa(self):
        rows = [{"x": float(i), "y": 2.0 * i + 1} for i in range(10)]
        result = correlate(rows, "x", "y")
        self.assertAlmostEqual(result["pearson_r"], 1.0)
        self.assertTrue(result["significant"])
        self.assertIn("se rechaza H0", result["interpretation"])

    def test_pocos_datos_no_calcula(self):
        result = correlate([{"x": 1.0, "y": 2.0}], "x", "y")
        self.assertIsNone(result["pearson_r"])
        self.assertIn("insuficientes", result["interpretation"])

    def test_dataset_calcula_porcentajes_y_marca_sinteticos(self):
        self._session_with_events(60, {"happy": 15, "neutral": 10, "sad": 5})
        today = timezone.localdate()
        rows = build_dataset(Venue.objects.all(), today - timedelta(days=1), today)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ts_minutes"], 60.0)
        self.assertEqual(rows[0]["positive_pct"], 50.0)
        self.assertAlmostEqual(rows[0]["negative_pct"], 16.67)
        self.assertTrue(rows[0]["synthetic"])
        self.assertEqual(build_dataset(Venue.objects.all(), today - timedelta(days=1), today,
                                       include_synthetic=False), [])

    def test_panel_y_exportacion_responden(self):
        for minutes, happy in ((40, 20), (60, 15), (80, 10), (100, 5)):
            self._session_with_events(minutes, {"happy": happy, "neutral": 30 - happy})
        self.client.force_login(self.user)
        response = self.client.get("/analytics/correlation/?synthetic=1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pearson r")
        self.assertContains(response, "no constituyen evidencia empírica")
        csv_response = self.client.get("/analytics/correlation/csv/?synthetic=1")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("Pearson r", csv_response.content.decode("utf-8"))

    def test_panel_excluye_camaras_demo_por_defecto(self):
        for minutes, happy in ((40, 20), (60, 15), (80, 10), (100, 5)):
            self._session_with_events(minutes, {"happy": happy, "neutral": 30 - happy})
        self.client.force_login(self.user)
        response = self.client.get("/analytics/correlation/")
        self.assertFalse(response.context["include_synthetic"])
        self.assertEqual(response.context["rows"], [])
        response = self.client.get("/analytics/correlation/?synthetic=1")
        self.assertTrue(response.context["include_synthetic"])
        self.assertEqual(len(response.context["rows"]), 4)
