from datetime import timedelta

import numpy as np
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from ai_vision.services.association import find_service_session
from ai_vision.services.vision_pipeline import (
    MODELS_DIR, FERPLUS_FILE, YUNET_FILE, EventWindow, VisionPipeline,
)
from authentication.models import Profile
from cameras.models import Camera
from operations.models import RestaurantTable, ServiceSession
from venues.models import Venue

MODELS_READY = (MODELS_DIR / YUNET_FILE).exists() and (MODELS_DIR / FERPLUS_FILE).exists()


class VisionPipelineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("analista", password="Test12345!", is_staff=True, is_superuser=True)
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.venue = Venue.objects.create(name="Local de prueba")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="X1", capacity=4)

    def test_asociacion_espacio_temporal_con_sesion_de_mesa(self):
        now = timezone.now()
        earlier = ServiceSession.objects.create(
            table=self.table, started_at=now - timedelta(hours=3), guests_count=2, status="closed",
        )
        ServiceSession.objects.filter(pk=earlier.pk).update(ended_at=now - timedelta(hours=2))
        current = ServiceSession.objects.create(
            table=self.table, started_at=now - timedelta(minutes=30), guests_count=2,
        )
        self.assertEqual(find_service_session(self.table, now), current)
        self.assertEqual(find_service_session(self.table, now - timedelta(hours=2, minutes=30)), earlier)
        self.assertIsNone(find_service_session(self.table, now - timedelta(hours=5)))
        self.assertIsNone(find_service_session(None, now))

    def test_ventana_agrega_distribucion_y_expresion_dominante(self):
        window = EventWindow()
        face = lambda emotion, conf: {"emotion": emotion, "emotion_confidence": conf, "detector_score": 0.9}
        window.add({"faces_count": 2, "processing_time_ms": 40, "faces": [face("happy", 0.8), face("neutral", 0.7)]})
        window.add({"faces_count": 1, "processing_time_ms": 50, "faces": [face("happy", 0.6)]})
        summary = window.summary()
        self.assertEqual(summary["estimated_emotion"], "happy")
        self.assertEqual(summary["emotion_distribution"], {"happy": 2, "neutral": 1})
        self.assertEqual(summary["faces_count"], 2)
        self.assertEqual(summary["processing_time_ms"], 45)
        self.assertAlmostEqual(summary["confidence"], 0.7)

    def test_pipeline_cumple_latencia_en_fotograma_vacio(self):
        if not MODELS_READY:
            self.skipTest("Modelos no descargados")
        pipeline = VisionPipeline()
        pipeline.analyze(np.zeros((480, 640, 3), dtype=np.uint8))  # calentamiento
        result = pipeline.analyze(np.zeros((480, 640, 3), dtype=np.uint8))
        self.assertEqual(result["faces_count"], 0)
        self.assertLess(result["processing_time_ms"], 200)

    def test_detalle_de_sesion_muestra_distribucion(self):
        camera = Camera.objects.create(venue=self.venue, name="Cam prueba", source="0", table=self.table)
        session = AnalysisSession.objects.create(camera=camera, status=AnalysisSession.Status.COMPLETED)
        DetectionEvent.objects.create(
            session=session, faces_count=1, estimated_emotion="happy",
            emotion_distribution={"happy": 3, "neutral": 1}, processing_time_ms=45,
        )
        self.client.force_login(self.user)
        response = self.client.get(f"/ai/sessions/{session.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Distribución agregada de expresiones")
        self.assertContains(response, "Positiva / feliz")

    def test_ventana_calcula_comportamiento_agregado(self):
        window = EventWindow()
        window.add({"faces_count": 2, "processing_time_ms": 30, "activity": 20.0, "faces": []})
        window.add({"faces_count": 0, "processing_time_ms": 30, "activity": 40.0, "faces": []})
        window.add({"faces_count": 3, "processing_time_ms": 30, "activity": None, "faces": []})
        summary = window.summary()
        self.assertEqual(summary["occupancy"], 2.0)
        self.assertAlmostEqual(summary["presence_ratio"], 2 / 3)
        self.assertEqual(summary["activity_level"], 30.0)

    def test_pipeline_mide_actividad_sin_clasificar(self):
        if not MODELS_READY:
            self.skipTest("Modelos no descargados")
        pipeline = VisionPipeline()
        first = pipeline.analyze(np.zeros((480, 640, 3), dtype=np.uint8), classify=False)
        second = pipeline.analyze(np.full((480, 640, 3), 255, dtype=np.uint8), classify=False)
        self.assertIsNone(first["activity"])
        self.assertGreater(second["activity"], 50)

    def test_ventana_calcula_valencia_y_atencion(self):
        window = EventWindow()
        face = lambda valence, away: {"emotion": "happy", "emotion_confidence": 0.8, "detector_score": 0.9,
                                      "valence": valence, "looking_away": away}
        window.add({"faces_count": 2, "processing_time_ms": 30, "faces": [face(0.6, False), face(0.2, True)]})
        window.add({"faces_count": 1, "processing_time_ms": 30, "faces": [face(None, False)]})
        summary = window.summary()
        self.assertAlmostEqual(summary["valence"], 0.4)
        self.assertAlmostEqual(summary["attention_seeking"], 1 / 3)

    def test_indice_de_experiencia(self):
        from ai_vision.services.experience import experience_index, valence_from_distribution
        self.assertEqual(experience_index(0.0, 0.0, 0), 70.0)
        self.assertGreater(experience_index(0.8, 0.0, 0), experience_index(-0.5, 0.4, 30))
        self.assertIsNone(experience_index(None, None, 5))
        self.assertAlmostEqual(valence_from_distribution({"happy": 1, "neutral": 1}), 0.5)
