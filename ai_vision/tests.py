from unittest.mock import patch

import numpy as np
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase

from ai_vision.management.commands.run_camera_analysis import Command
from ai_vision.models import AnalysisSession, DetectionEvent
from cameras.models import Camera
from operations.models import RestaurantTable, ServiceSession
from venues.models import Venue

COMMAND = "ai_vision.management.commands.run_camera_analysis"


def fake_result(emotion=None):
    faces = []
    if emotion:
        faces = [{"box": {"x": 0, "y": 0, "width": 30, "height": 30}, "detector_score": 0.9,
                  "emotion": emotion, "emotion_confidence": 0.8}]
    return {"faces_count": len(faces), "faces": faces, "processing_time_ms": 5}


class RunCameraAnalysisTests(TransactionTestCase):
    """Comando de análisis con cámara y modelos simulados (sin webcam real)."""

    def setUp(self):
        venue = Venue.objects.create(name="Local de prueba")
        self.table = RestaurantTable.objects.create(venue=venue, code="X1", capacity=4)
        self.camera = Camera.objects.create(venue=venue, name="Cam prueba", source="0", table=self.table)
        self.session = AnalysisSession.objects.create(camera=self.camera, status=AnalysisSession.Status.PENDING)

    def _prepare(self, capture_factory, pipeline_factory, emotion=None):
        capture = capture_factory.return_value
        capture.isOpened.return_value = True
        capture.read.return_value = (True, np.zeros((10, 10, 3), dtype=np.uint8))
        pipeline_factory.return_value.analyze.return_value = fake_result(emotion)
        return capture

    @patch(f"{COMMAND}.VisionPipeline")
    @patch(f"{COMMAND}.cv2.VideoCapture")
    def test_revocacion_de_autorizacion_detiene_sin_guardar_eventos(self, capture_factory, pipeline_factory):
        capture = self._prepare(capture_factory, pipeline_factory)
        # 1) verificación inicial, 2) primer control del bucle, 3) segundo control: revocada
        with patch.object(Command, "policy_is_authorized", side_effect=[True, True, False]):
            with self.assertRaisesRegex(CommandError, "autorización visual ya no está vigente"):
                call_command("run_camera_analysis", self.session.id, "--sample-every", "2",
                             "--max-frames", "10", "--check-every-seconds", "0", "--no-preview")

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, AnalysisSession.Status.FAILED)
        self.assertEqual(pipeline_factory.return_value.analyze.call_count, 1)
        self.assertFalse(DetectionEvent.objects.exists())
        capture.release.assert_called_once()

    @patch(f"{COMMAND}.VisionPipeline")
    @patch(f"{COMMAND}.cv2.VideoCapture")
    def test_eventos_guardan_expresion_y_se_asocian_a_la_mesa(self, capture_factory, pipeline_factory):
        self._prepare(capture_factory, pipeline_factory, emotion="happy")
        service = ServiceSession.objects.create(table=self.table, guests_count=2)
        with patch.object(Command, "policy_is_authorized", return_value=True):
            call_command("run_camera_analysis", self.session.id, "--sample-every", "2",
                         "--max-frames", "4", "--no-preview")

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, AnalysisSession.Status.COMPLETED)
        self.assertEqual(self.session.frames_processed, 4)
        events = DetectionEvent.objects.filter(session=self.session)
        self.assertEqual(events.count(), 2)
        for event in events:
            self.assertEqual(event.estimated_emotion, "happy")
            self.assertEqual(event.emotion_distribution, {"happy": 2})
            self.assertEqual(event.table, self.table)
            self.assertEqual(event.service_session, service)
