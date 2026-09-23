import time

import cv2
from django.core.management.base import BaseCommand, CommandError

from ai_vision.models import AnalysisSession, DetectionEvent
from ai_vision.services.face_detector import HaarFaceDetector
from cameras.models import Camera
from monitoring.models import AuditLog
from privacy.models import PrivacyPolicy


class Command(BaseCommand):
    help = (
        "Ejecuta detección facial agregada sobre una cámara registrada. "
        "Presiona Q en la ventana de OpenCV para detener."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "camera_id",
            type=int,
            help="ID de la cámara registrada en Django Admin.",
        )

        parser.add_argument(
            "--sample-every",
            type=int,
            default=15,
            help=(
                "Guardar un evento agregado cada N frames. "
                "Por defecto: 15."
            ),
        )

        parser.add_argument(
            "--max-frames",
            type=int,
            default=0,
            help=(
                "Detener tras N frames. "
                "El valor 0 significa sin límite."
            ),
        )

        parser.add_argument(
            "--duration",
            type=int,
            default=0,
            help=(
                "Duración máxima del análisis en segundos. "
                "El valor 0 significa sin límite."
            ),
        )

        parser.add_argument(
            "--no-preview",
            action="store_true",
            help=(
                "Ejecuta el análisis sin abrir la ventana de OpenCV. "
                "Útil para pruebas sin interfaz gráfica."
            ),
        )

    def get_capture_source(self, camera_model):
        """
        Convierte la fuente configurada en el formato requerido por OpenCV.

        - Webcam: índice entero, por ejemplo 0.
        - IP/RTSP/archivo: URL o ruta configurada en Camera.source.
        """
        source = camera_model.source

        if camera_model.source_type == Camera.SourceType.WEBCAM:
            try:
                return int(source)
            except (TypeError, ValueError) as exc:
                raise CommandError(
                    "Una webcam debe tener un origen numérico, "
                    "por ejemplo: 0."
                ) from exc

        return source

    def create_audit_log(self, session, action, description):
        """
        Centraliza la creación de eventos de auditoría técnicos.
        """
        return AuditLog.objects.create(
            user=None,
            venue=session.camera.venue,
            action=action,
            module="ai_vision",
            object_type="AnalysisSession",
            object_id=str(session.id),
            description=description,
        )

    def handle(self, *args, **options):
        camera_id = options["camera_id"]
        sample_every = max(1, options["sample_every"])
        max_frames = max(0, options["max_frames"])
        duration = max(0, options["duration"])
        preview_enabled = not options["no_preview"]

        try:
            camera_model = Camera.objects.get(
                id=camera_id,
                is_active=True,
            )
        except Camera.DoesNotExist as exc:
            raise CommandError(
                "No existe una cámara activa con ese ID."
            ) from exc

        try:
            privacy_policy = camera_model.venue.privacy_policy
        except PrivacyPolicy.DoesNotExist as exc:
            raise CommandError(
                "No existe una política de privacidad configurada "
                "para el local asociado a esta cámara."
            ) from exc

        if not privacy_policy.is_processing_authorized:
            raise CommandError(
                "El análisis visual está bloqueado por privacidad. "
                "Verifica que la política esté habilitada, que no se "
                "almacenen imágenes originales y que exista una "
                "autorización vigente."
            )

        source = self.get_capture_source(camera_model)

        if camera_model.source_type == Camera.SourceType.WEBCAM:
            capture = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        else:
            capture = cv2.VideoCapture(source)

        if not capture.isOpened():
            raise CommandError(
                "No se pudo abrir la fuente configurada: "
                f"{camera_model.source}"
            )

        detector = HaarFaceDetector()

        session = AnalysisSession.objects.create(
            camera=camera_model
        )

        started_audit = self.create_audit_log(
            session=session,
            action=AuditLog.Action.START,
            description=(
                "El sistema inició el procesamiento técnico de "
                f"la sesión de análisis #{session.id}."
            ),
        )

        session.start()

        self.stdout.write(
            self.style.SUCCESS(
                f"Sesión #{session.id} iniciada para: "
                f"{camera_model.name}"
            )
        )

        self.stdout.write(
            f"Fuente: {camera_model.source} | "
            f"Guardado cada {sample_every} frames"
        )

        if duration > 0:
            self.stdout.write(
                f"Duración máxima configurada: {duration} segundos."
            )

        frame_number = 0
        total_faces = 0
        started_at = time.monotonic()
        last_event_time = started_at
        session_failed = False
        error_message = ""

        try:
            while True:
                success, frame = capture.read()

                if not success:
                    raise RuntimeError(
                        "No fue posible leer un frame de la cámara."
                    )

                frame_number += 1

                result = detector.detect(frame)
                faces_count = result["faces_count"]
                total_faces += faces_count

                for box in result["boxes"]:
                    x = box["x"]
                    y = box["y"]
                    width = box["width"]
                    height = box["height"]

                    cv2.rectangle(
                        frame,
                        (x, y),
                        (x + width, y + height),
                        (0, 255, 0),
                        2,
                    )

                elapsed_seconds = time.monotonic() - started_at
                fps = (
                    frame_number / elapsed_seconds
                    if elapsed_seconds > 0
                    else 0
                )

                cv2.putText(
                    frame,
                    f"Rostros: {faces_count}",
                    (15, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2,
                )

                cv2.putText(
                    frame,
                    f"Frames: {frame_number} | FPS: {fps:.1f}",
                    (15, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 0),
                    2,
                )

                if duration > 0:
                    cv2.putText(
                        frame,
                        f"Tiempo: {elapsed_seconds:.0f}/{duration}s",
                        (15, 90),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 0),
                        2,
                    )

                if preview_enabled:
                    cv2.imshow(
                        "GastroInsight AI - Analisis de prueba",
                        frame,
                    )

                if frame_number % sample_every == 0:
                    DetectionEvent.objects.create(
                        session=session,
                        faces_count=faces_count,
                        processing_time_ms=result[
                            "processing_time_ms"
                        ],
                    )

                    last_event_time = time.monotonic()

                if max_frames > 0 and frame_number >= max_frames:
                    self.stdout.write(
                        "Límite máximo de frames alcanzado."
                    )
                    break

                if duration > 0 and elapsed_seconds >= duration:
                    self.stdout.write(
                        "Duración máxima de análisis alcanzada."
                    )
                    break

                if preview_enabled:
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        self.stdout.write(
                            "Análisis detenido manualmente por usuario."
                        )
                        break

        except Exception as exc:
            session_failed = True
            error_message = str(exc)

        finally:
            capture.release()

            if preview_enabled:
                cv2.destroyAllWindows()

        session.frames_processed = frame_number
        session.total_faces_detected = total_faces

        if session_failed:
            session.finish(
                status=AnalysisSession.Status.FAILED,
                error_message=error_message,
            )

            self.create_audit_log(
                session=session,
                action=AuditLog.Action.STOP,
                description=(
                    "El sistema finalizó con error la sesión de "
                    f"análisis #{session.id}. Error: {error_message}"
                ),
            )

            raise CommandError(
                f"La sesión #{session.id} falló: {error_message}"
            )

        stopped_audit = self.create_audit_log(
            session=session,
            action=AuditLog.Action.STOP,
            description=(
                "La sesión finalizó porque se alcanzó "
                "la duración máxima configurada."
            ),
        )

        session.finish(
            status=AnalysisSession.Status.COMPLETED,
        )

        elapsed_seconds = time.monotonic() - started_at
        average_fps = (
            frame_number / elapsed_seconds
            if elapsed_seconds > 0
            else 0
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Sesión #{session.id} completada correctamente."
            )
        )
        self.stdout.write(f"Frames procesados: {frame_number}")
        self.stdout.write(f"Rostros acumulados: {total_faces}")
        self.stdout.write(
            f"Duración real: {elapsed_seconds:.2f} segundos"
        )
        self.stdout.write(
            f"FPS promedio: {average_fps:.2f}"
        )