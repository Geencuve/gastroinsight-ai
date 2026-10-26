from django.test import TestCase
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from ai_vision.management.commands.run_camera_analysis import Command
from ai_vision.models import AnalysisSession
from cameras.models import Camera
# Create your tests here.
class CameraAuthorizationDuringRunTests(SimpleTestCase):
    @patch(
        "ai_vision.management.commands.run_camera_analysis."
        "DetectionEvent.objects.create"
    )
    @patch(
        "ai_vision.management.commands.run_camera_analysis."
        "AnalysisSession.objects.create"
    )
    @patch(
        "ai_vision.management.commands.run_camera_analysis."
        "Camera.objects.get"
    )
    @patch(
        "ai_vision.management.commands.run_camera_analysis."
        "HaarFaceDetector"
    )
    @patch(
        "ai_vision.management.commands.run_camera_analysis."
        "cv2.putText"
    )
    @patch(
        "ai_vision.management.commands.run_camera_analysis."
        "cv2.VideoCapture"
    )
    @patch.object(Command, "create_audit_log")
    def test_revocation_stops_before_next_event(
        self,
        mock_audit,
        mock_capture_factory,
        mock_put_text,
        mock_detector_factory,
        mock_camera_get,
        mock_session_create,
        mock_event_create,
    ):
        class ChangingPolicy:
            processing_enabled = True
            store_original_images = False

            def __init__(self):
                self.checks = 0

            def refresh_from_db(self, **kwargs):
                pass

            @property
            def is_processing_authorized(self):
                self.checks += 1
                return self.checks < 3

        policy = ChangingPolicy()
        camera = SimpleNamespace(
            source="0",
            source_type=Camera.SourceType.WEBCAM,
            name="Cámara de prueba",
            is_active=True,
            venue=SimpleNamespace(privacy_policy=policy),
            refresh_from_db=MagicMock(),
        )
        mock_camera_get.return_value = camera

        capture = mock_capture_factory.return_value
        capture.isOpened.return_value = True
        capture.read.return_value = (True, object())

        detector = mock_detector_factory.return_value
        detector.detect.return_value = {
            "faces_count": 0,
            "boxes": [],
            "processing_time_ms": 1,
        }

        session = mock_session_create.return_value
        session.id = 1

        with self.assertRaisesRegex(
            CommandError,
            "autorización visual ya no está vigente",
        ):
            Command().handle(
                camera_id=1,
                sample_every=2,
                max_frames=2,
                duration=0,
                no_preview=True,
            )

        self.assertEqual(detector.detect.call_count, 1)
        mock_event_create.assert_not_called()
        session.finish.assert_called_once()
        self.assertEqual(
            session.finish.call_args.kwargs["status"],
            AnalysisSession.Status.FAILED,
        )
        capture.release.assert_called_once()