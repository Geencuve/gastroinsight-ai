import time
from collections import Counter
from datetime import timedelta

import cv2
from django.db import transaction
from django.utils import timezone

from cameras.models import Camera

try:
    from ai_vision.models import AnalysisSession, AnalysisEvent
except ImportError:
    AnalysisSession = None
    AnalysisEvent = None

try:
    from .face_detector import FaceDetector
except ImportError:
    FaceDetector = None


class CameraAnalyzer:
    """
    Servicio principal para analizar una cámara registrada.

    Flujo:
    Camera -> OpenCV VideoCapture -> FaceDetector -> AnalysisEvent -> AnalysisSession
    """

    def __init__(
        self,
        camera_id,
        duration_seconds=60,
        process_every_n_frames=5,
        preview=False,
    ):
        self.camera_id = camera_id
        self.duration_seconds = duration_seconds
        self.process_every_n_frames = max(process_every_n_frames, 1)
        self.preview = preview

        self.camera = None
        self.capture = None
        self.session = None

        self.frames_read = 0
        self.frames_processed = 0
        self.faces_detected = 0
        self.events_created = 0
        self.expression_counter = Counter()

    def get_camera_source(self):
        """
        Obtiene el origen de video desde el modelo Camera.

        El proyecto puede usar nombres de campo diferentes, por eso se
        revisan alternativas comunes.
        """
        possible_fields = [
            "stream_url",
            "url",
            "rtsp_url",
            "video_url",
            "source",
        ]

        source = None

        for field_name in possible_fields:
            value = getattr(self.camera, field_name, None)

            if value:
                source = value
                break

        if source is None:
            return 0

        source = str(source).strip()

        if source.isdigit():
            return int(source)

        username = getattr(self.camera, "username", None)
        password = getattr(self.camera, "password", None)

        if (
            username
            and password
            and "://" in source
            and "@" not in source
        ):
            protocol, remainder = source.split("://", 1)
            source = f"{protocol}://{username}:{password}@{remainder}"

        return source

    def create_session(self):
        """
        Crea una sesión solo si el modelo AnalysisSession está disponible.

        Incluye variantes de campos para no romper si el modelo todavía
        tiene una estructura distinta.
        """
        if AnalysisSession is None:
            return None

        fields = {
            field.name
            for field in AnalysisSession._meta.get_fields()
        }

        data = {}

        if "camera" in fields:
            data["camera"] = self.camera

        if "status" in fields:
            data["status"] = "running"

        if "started_at" in fields:
            data["started_at"] = timezone.now()

        try:
            return AnalysisSession.objects.create(**data)
        except Exception as error:
            print(f"Advertencia: no se pudo crear AnalysisSession: {error}")
            return None

    def finish_session(self):
        """Marca la sesión como completada cuando el modelo lo permite."""
        if not self.session:
            return

        try:
            fields = {
                field.name
                for field in self.session._meta.get_fields()
            }

            if "status" in fields:
                self.session.status = "completed"

            if "ended_at" in fields:
                self.session.ended_at = timezone.now()

            self.session.save()
        except Exception as error:
            print(f"Advertencia: no se pudo cerrar AnalysisSession: {error}")

    def create_event(self, expression, confidence, metadata):
        """
        Guarda un evento detectado. No detiene el análisis si el modelo
        no contiene todavía todos los campos esperados.
        """
        if not self.session or AnalysisEvent is None:
            return

        fields = {
            field.name
            for field in AnalysisEvent._meta.get_fields()
        }

        data = {}

        if "session" in fields:
            data["session"] = self.session

        if "expression_type" in fields:
            data["expression_type"] = expression
        elif "expression" in fields:
            data["expression"] = expression
        elif "label" in fields:
            data["label"] = expression

        if "confidence" in fields:
            data["confidence"] = confidence

        if "created_at" in fields:
            data["created_at"] = timezone.now()

        if "metadata" in fields:
            data["metadata"] = metadata

        try:
            AnalysisEvent.objects.create(**data)
            self.events_created += 1
        except Exception as error:
            print(f"Advertencia: no se pudo guardar evento: {error}")

    def process_detection(self, detection, frame_number):
        """
        Procesa una detección entregada por FaceDetector.

        El detector puede retornar:
        - Un diccionario.
        - Una lista de diccionarios.
        - Una estructura diferente durante la etapa inicial.

        Por eso se usa una interpretación segura.
        """
        if not detection:
            return

        if isinstance(detection, dict):
            detections = [detection]
        elif isinstance(detection, list):
            detections = detection
        else:
            detections = []

        for item in detections:
            if not isinstance(item, dict):
                continue

            expression = item.get("expression", "neutral")
            confidence = float(item.get("confidence", 0.0))
            bbox = item.get("bbox", [])

            self.faces_detected += 1
            self.expression_counter[expression] += 1

            metadata = {
                "frame_number": frame_number,
                "bbox": bbox,
                "camera_id": self.camera.id,
                "camera_name": self.camera.name,
            }

            self.create_event(
                expression=expression,
                confidence=confidence,
                metadata=metadata,
            )

    def analyze(self):
        """
        Ejecuta una sesión completa de análisis.

        Returns:
            dict con el resumen de resultados.
        """
        self.camera = Camera.objects.get(pk=self.camera_id)
        source = self.get_camera_source()

        print("=" * 60)
        print("ANÁLISIS DE CÁMARA - GASTROINSIGHT AI")
        print("=" * 60)
        print(f"Cámara: {self.camera.name}")
        print(f"Origen: {source}")
        print(f"Duración: {self.duration_seconds} segundos")
        print(f"Procesar cada: {self.process_every_n_frames} frames")
        print("=" * 60)

        self.capture = cv2.VideoCapture(source)

        if not self.capture.isOpened():
            raise RuntimeError(
                f"No fue posible abrir la cámara '{self.camera.name}'."
            )

        detector = FaceDetector() if FaceDetector else None
        self.session = self.create_session()

        started_at = timezone.now()
        deadline = time.monotonic() + self.duration_seconds

        try:
            while time.monotonic() < deadline:
                success, frame = self.capture.read()

                if not success:
                    print("Advertencia: no se pudo obtener un frame.")
                    time.sleep(0.2)
                    continue

                self.frames_read += 1

                if self.frames_read % self.process_every_n_frames != 0:
                    continue

                self.frames_processed += 1

                if detector:
                    detections = detector.detect(frame)
                    self.process_detection(
                        detection=detections,
                        frame_number=self.frames_read,
                    )

                if self.preview:
                    cv2.imshow(
                        f"Analizando: {self.camera.name}",
                        frame,
                    )

                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        print("Análisis detenido manualmente con la tecla Q.")
                        break

        finally:
            if self.capture:
                self.capture.release()

            if self.preview:
                cv2.destroyAllWindows()

            self.finish_session()

        finished_at = timezone.now()

        dominant_expression = (
            self.expression_counter.most_common(1)[0][0]
            if self.expression_counter
            else "sin_detecciones"
        )

        result = {
            "camera_id": self.camera.id,
            "camera_name": self.camera.name,
            "started_at": started_at.isoformat(),
            "ended_at": finished_at.isoformat(),
            "duration_seconds": round(
                (finished_at - started_at).total_seconds(),
                2,
            ),
            "frames_read": self.frames_read,
            "frames_processed": self.frames_processed,
            "faces_detected": self.faces_detected,
            "events_created": self.events_created,
            "dominant_expression": dominant_expression,
            "expressions": dict(self.expression_counter),
            "session_id": self.session.id if self.session else None,
        }

        print("\n" + "=" * 60)
        print("RESUMEN DEL ANÁLISIS")
        print("=" * 60)
        print(f"Frames leídos: {result['frames_read']}")
        print(f"Frames procesados: {result['frames_processed']}")
        print(f"Rostros detectados: {result['faces_detected']}")
        print(f"Eventos registrados: {result['events_created']}")
        print(f"Expresión predominante: {result['dominant_expression']}")
        print("=" * 60)

        return result