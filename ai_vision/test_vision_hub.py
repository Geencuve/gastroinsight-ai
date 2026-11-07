from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from ai_vision.models import AnalysisSession, DetectionEvent
from ai_vision.services.vision_pipeline import EventWindow
from assistant_chat.services import build_staff_response
from authentication.models import Profile
from cameras.models import Camera
from monitoring.models import AuditLog
from operations.models import RestaurantTable
from venues.models import Venue


class VisionHubTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local de prueba")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="M1", capacity=4, zone_name="Salón")
        self.camera = Camera.objects.create(venue=self.venue, name="Cam M1", source="demo",
                                            source_type=Camera.SourceType.DEMO, table=self.table)
        analysis = AnalysisSession.objects.create(camera=self.camera, status="running")
        DetectionEvent.objects.create(session=analysis, faces_count=2, table=self.table, occupancy=Decimal("2"),
                                      experience_index=Decimal("70"),
                                      scene_boxes=[[0.5, 0.55, 0.36, 0.28, "t"], [0.3, 0.55, 0.12, 0.3, "p"]])

    def _user(self, name, role):
        user = User.objects.create_user(name, password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(self.venue)
        return user

    def test_interfaz_unica_con_pestanas_segun_rol(self):
        self.client.force_login(self._user("supervisora", Profile.Role.SUPERVISOR))
        response = self.client.get("/vision/")
        self.assertContains(response, "Monitor en vivo")
        self.assertContains(response, 'data-src="/ai/monitor/?embed=1"')
        self.assertNotContains(response, "Entrenamiento")
        self.client.force_login(self._user("garzon", Profile.Role.WAITER))
        self.assertEqual(self.client.get("/vision/").status_code, 403)

    def test_datos_de_miniaturas_con_cajas(self):
        self.client.force_login(self._user("supervisor", Profile.Role.SUPERVISOR))
        item = self.client.get("/vision/camaras/datos/").json()["cameras"][0]
        self.assertEqual(item["name"], "Cam M1")
        self.assertEqual(len(item["boxes"]), 2)
        self.assertTrue(item["live_url"].endswith("/vivo/"))

    def test_vista_en_vivo_solo_roles_autorizados_y_auditada(self):
        self.client.force_login(self._user("operador", Profile.Role.OPERATOR))
        data = self.client.post(f"/vision/camaras/{self.camera.id}/vivo/").json()
        self.assertFalse(data["available"])
        self.assertIn("demostración", data["reason"])
        webcam = Camera.objects.create(venue=self.venue, name="Webcam", source="0", source_type=Camera.SourceType.WEBCAM)
        data = self.client.post(f"/vision/camaras/{webcam.id}/vivo/").json()
        self.assertTrue(data["available"])
        self.assertTrue(AuditLog.objects.filter(description__icontains="vista en vivo").exists())
        self.client.force_login(self._user("visor", Profile.Role.VIEWER))
        self.assertEqual(self.client.post(f"/vision/camaras/{webcam.id}/vivo/").status_code, 403)

    def test_ventana_guarda_las_ultimas_cajas(self):
        window = EventWindow()
        window.add({"faces_count": 1, "processing_time_ms": 30, "faces": [],
                    "scene": {"persons": 1, "tables": 1, "ms": 300, "boxes": [[0.5, 0.5, 0.2, 0.3, "p"]]}})
        self.assertEqual(window.summary()["scene_boxes"], [[0.5, 0.5, 0.2, 0.3, "p"]])

    def test_sazon_responde_con_miniaturas(self):
        supervisor = self._user("sup", Profile.Role.SUPERVISOR)
        _, intent, meta = build_staff_response(supervisor, "¿Cómo están las mediciones por cámara?")
        self.assertEqual(intent, "camera_metrics")
        self.assertEqual(meta["thumbs"][0]["name"], "Cam M1")

    def test_modo_incrustado(self):
        self.client.force_login(self._user("sup2", Profile.Role.SUPERVISOR))
        self.assertContains(self.client.get("/ai/monitor/?embed=1"), 'data-embed="1"')
