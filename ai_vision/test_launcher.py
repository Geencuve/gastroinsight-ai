from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from ai_vision.models import AnalysisSession
from authentication.models import Profile
from cameras.models import Camera
from operations.models import RestaurantTable
from venues.models import Venue


class LaunchFromInterfaceTests(TestCase):
    """El análisis se crea e inicia desde la interfaz, sin usar la terminal."""

    def setUp(self):
        user = User.objects.create_user("operador", password="Test12345!", is_staff=True, is_superuser=True)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        venue = Venue.objects.create(name="Local de prueba")
        table = RestaurantTable.objects.create(venue=venue, code="X1", capacity=4)
        self.webcam = Camera.objects.create(venue=venue, name="Webcam", source="0", table=table)
        self.demo = Camera.objects.create(venue=venue, name="Cam demo", source="demo",
                                          source_type=Camera.SourceType.DEMO)
        self.client.force_login(user)

    @patch("ai_vision.views.launch_analysis", return_value=(4321, Path("logs/analisis.log")))
    def test_iniciar_lanza_el_analisis_y_redirige_al_detalle(self, launch):
        session = AnalysisSession.objects.create(camera=self.webcam, status=AnalysisSession.Status.PENDING)
        response = self.client.post(f"/ai/sessions/{session.id}/start/", {"preview": "1", "duration": "60"})
        self.assertRedirects(response, f"/ai/sessions/{session.id}/", fetch_redirect_response=False)
        launch.assert_called_once_with(session.id, preview=True, duration=60)

    @patch("ai_vision.views.launch_analysis")
    def test_camara_demo_no_lanza_procesamiento(self, launch):
        session = AnalysisSession.objects.create(camera=self.demo, status=AnalysisSession.Status.PENDING)
        self.client.post(f"/ai/sessions/{session.id}/start/", {"duration": "60"})
        launch.assert_not_called()

    def test_lista_muestra_acciones_y_marca_camaras_demo(self):
        AnalysisSession.objects.create(camera=self.webcam, status=AnalysisSession.Status.PENDING)
        response = self.client.get("/ai/sessions/")
        self.assertContains(response, "Crear sesión")
        self.assertContains(response, "Iniciar análisis")
        self.assertContains(response, "Datos sintéticos de demostración")
        self.assertContains(response, "Panel de correlación")

    def test_lista_muestra_cantidad_de_eventos(self):
        from ai_vision.models import DetectionEvent
        session = AnalysisSession.objects.create(camera=self.webcam, status=AnalysisSession.Status.COMPLETED)
        for _ in range(3):
            DetectionEvent.objects.create(session=session, faces_count=1)
        response = self.client.get("/ai/sessions/")
        self.assertEqual(response.context["sessions"][0].events_count, 3)
