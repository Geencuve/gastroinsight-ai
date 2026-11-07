from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from ai_vision.models import AnalysisSession, DetectionEvent
from ai_vision.services.camera_metrics import camera_measurements
from ai_vision.services.indices import INDEX_DEFINITIONS
from ai_vision.services.vision_pipeline import EventWindow
from authentication.models import Profile
from cameras.models import Camera
from operations.models import EnvironmentReading, InfrastructureReport, RestaurantTable
from venues.models import Venue


class SupervisorTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local de prueba")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="M1", capacity=4)
        self.user = User.objects.create_user("jefe", password="Test12345!", is_superuser=True, is_staff=True)
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.camera = Camera.objects.create(venue=self.venue, name="Cam salón", source="demo",
                                            source_type=Camera.SourceType.DEMO, table=self.table)

    def test_ventana_agrega_personas_y_mesas_de_yolo26(self):
        window = EventWindow()
        window.add({"faces_count": 1, "processing_time_ms": 30, "faces": [], "scene": {"persons": 3, "tables": 1, "ms": 400}})
        window.add({"faces_count": 1, "processing_time_ms": 30, "faces": [], "scene": {"persons": 3, "tables": 1, "ms": 410}})
        window.add({"faces_count": 1, "processing_time_ms": 30, "faces": []})
        summary = window.summary()
        self.assertEqual(summary["persons_detected"], 3.0)
        self.assertEqual(summary["tables_detected"], 1.0)

    def test_mediciones_por_camara(self):
        analysis = AnalysisSession.objects.create(camera=self.camera, status="running")
        for _ in range(2):
            DetectionEvent.objects.create(session=analysis, faces_count=2, table=self.table, occupancy=Decimal("2"),
                                          persons_detected=Decimal("4"), tables_detected=Decimal("1"),
                                          experience_index=Decimal("72"), valence=Decimal("0.3"))
        row = camera_measurements(Venue.objects.all())[0]
        self.assertTrue(row["live"])
        self.assertEqual(row["readings"], 2)
        self.assertEqual(row["scene_people"], 4.0)
        self.assertEqual(row["ieo"], 72.0)

    def test_panel_del_supervisor_y_registros(self):
        self.client.force_login(self.user)
        response = self.client.get("/supervisor/")
        self.assertContains(response, "Mediciones por cámara")
        self.assertContains(response, "Cómo se calculan los índices")
        self.client.post("/supervisor/ambiente/", {"zone": "Terraza", "lighting": "4", "noise": "2", "temperature_c": "21,5"})
        reading = EnvironmentReading.objects.get()
        self.assertEqual((reading.zone, reading.lighting, float(reading.temperature_c)), ("Terraza", 4, 21.5))
        self.client.post("/supervisor/infraestructura/", {"area": "restrooms", "description": "Falta papel"})
        report = InfrastructureReport.objects.get()
        self.client.post(f"/supervisor/infraestructura/{report.id}/resolver/")
        report.refresh_from_db()
        self.assertEqual(report.status, "resolved")

    def test_indices_definidos(self):
        self.assertEqual([i["code"] for i in INDEX_DEFINITIONS], ["IBE", "IEO", "Ts", "CSAT"])

    def test_supervisor_llega_a_su_panel(self):
        user = User.objects.create_user("supervisora", password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.SUPERVISOR
        profile.save()
        profile.venues.add(self.venue)
        self.client.force_login(user)
        self.assertRedirects(self.client.get("/"), "/supervisor/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/supervisor/").status_code, 200)
