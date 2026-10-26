import time

import cv2
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from ai_vision.services.face_detector import HaarFaceDetector
from cameras.models import Camera
from monitoring.models import AuditLog
from privacy.models import PrivacyPolicy


class Command(BaseCommand):
    help = (
        "Ejecuta detección facial agregada para una sesión pendiente creada "
        "desde la interfaz. Presiona Q en la ventana de OpenCV para detener."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "session_id",
            type=int,
            help="ID de la sesión pendiente creada desde la interfaz.",
        )
        parser.add_argument(
            "--sample-every",
            type=int,
            default=15,
            help="Guardar un evento agregado cada N frames. Por defecto: 15.",
        )
        parser.add_argument(
            "--max-frames",
            type=int,
            default=0,
            help="Detener tras N frames; 0 significa sin límite.",
        )
        parser.add_argument(
            "--duration",
            type=int,
            default=0,
            help="Duración máxima en segundos; 0 significa sin límite.",
        )
        parser.add_argument(
            "--no-preview",
            action="store_true",
            help="Ejecutar sin abrir una ventana de OpenCV.",
        )

    def get_capture_source(self, camera):
        source = camera.source
        if source is None or not str(source).strip():
            raise CommandError("La cámara no tiene un origen configurado.")
        source = str(source).strip()
        if camera.source_type == Camera.SourceType.WEBCAM:
            if not source.isdigit():
                raise CommandError(
                    "Una webcam debe tener un origen numérico, por ejemplo: 0."
                )
            return int(source)
        return source

    def create_audit_log(self, session, action, description):
        return AuditLog.objects.create(
            user=None,
            venue=session.camera.venue,
            action=action,
            module="ai_vision",
            object_type="AnalysisSession",
            object_id=str(session.id),
            description=description,
        )

    def session_is_running(self, session_id):
        close_old_connections()
        return AnalysisSession.objects.filter(
            pk=session_id,
            status=AnalysisSession.Status.RUNNING,
        ).exists()

    def policy_is_authorized(self, venue_id):
        close_old_connections()
        try:
            policy = PrivacyPolicy.objects.get(venue_id=venue_id)
        except PrivacyPolicy.DoesNotExist:
            return False
        return policy.is_processing_authorized

    def finish_if_running(
        self, session_id, status, frame_number, total_faces, error_message=""
    ):
        """Finaliza solo si nadie (por ejemplo, stop_session) ya cambió el estado."""
        return AnalysisSession.objects.filter(
            pk=session_id,
            status=AnalysisSession.Status.RUNNING,
        ).update(
            status=status,
            ended_at=timezone.now(),
            error_message=error_message,
            frames_processed=frame_number,
            total_faces_detected=total_faces,
        )

    def handle(self, *args, **options):
        session_id = options["session_id"]
        sample_every = max(1, options["sample_every"])
        max_frames = max(0, options["max_frames"])
        duration = max(0, options["duration"])
        preview_enabled = not options["no_preview"]

        try:
            session = AnalysisSession.objects.select_related("camera", "camera__venue").get(
                pk=session_id
            )
        except AnalysisSession.DoesNotExist as exc:
            raise CommandError("No existe una sesión con ese ID.") from exc

        camera = session.camera
        if not camera.is_active or not camera.venue.is_active:
            raise CommandError("La cámara o su local están inactivos.")
        if session.status != AnalysisSession.Status.PENDING:
            raise CommandError("La sesión ya no está pendiente.")
        if not self.policy_is_authorized(camera.venue_id):
            raise CommandError(
                "El análisis visual está bloqueado por privacidad. Verifica la "
                "política, el almacenamiento de imágenes y la autorización vigente."
            )

        source = self.get_capture_source(camera)
        if camera.source_type == Camera.SourceType.WEBCAM:
            capture = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        else:
            capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            capture.release()
            raise CommandError(
                f"No se pudo abrir la fuente configurada: {camera.source}"
            )

        claimed = AnalysisSession.objects.filter(
            pk=session.pk, status=AnalysisSession.Status.PENDING
        ).update(
            status=AnalysisSession.Status.RUNNING,
            started_at=timezone.now(),
            ended_at=None,
            error_message="",
            frames_processed=0,
            total_faces_detected=0,
        )
        if not claimed:
            capture.release()
            raise CommandError("La sesión dejó de estar pendiente antes de iniciar.")

        session.refresh_from_db()
        self.create_audit_log(
            session=session,
            action=AuditLog.Action.START,
            description=(
                f"El sistema inició el procesamiento técnico de la sesión de "
                f"análisis #{session.id}."
            ),
        )
        detector = HaarFaceDetector()
        self.stdout.write(
            self.style.SUCCESS(
                f"Sesión #{session.id} iniciada para: {camera.name}"
            )
        )
        self.stdout.write(
            f"Fuente: {camera.source} | Guardado cada {sample_every} frames"
        )

        frame_number = 0
        total_faces = 0
        started_at = time.monotonic()
        stop_reason = ""
        failure_message = ""

        try:
            while True:
                if not self.session_is_running(session.id):
                    stop_reason = "detenida desde la interfaz"
                    break
                close_old_connections()
                camera.refresh_from_db(fields=["is_active"])
                if not camera.is_active:
                    failure_message = "Procesamiento detenido: la cámara fue desactivada."
                    break
                if not self.policy_is_authorized(camera.venue_id):
                    failure_message = (
                        "Procesamiento detenido: la autorización visual ya no está vigente."
                    )
                    break

                success, frame = capture.read()
                if not success:
                    failure_message = "No fue posible leer un frame de la cámara."
                    break

                frame_number += 1
                result = detector.detect(frame)
                faces_count = result["faces_count"]
                total_faces += faces_count

                if preview_enabled:
                    for box in result["boxes"]:
                        x, y = box["x"], box["y"]
                        width, height = box["width"], box["height"]
                        cv2.rectangle(
                            frame, (x, y), (x + width, y + height), (0, 255, 0), 2
                        )

                    elapsed_seconds = time.monotonic() - started_at
                    fps = frame_number / elapsed_seconds if elapsed_seconds > 0 else 0
                    cv2.putText(
                        frame, f"Rostros: {faces_count}", (15, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2,
                    )
                    cv2.putText(
                        frame, f"Frames: {frame_number} | FPS: {fps:.1f}", (15, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2,
                    )
                    cv2.imshow("GastroInsight AI - Analisis de prueba", frame)

                if frame_number % sample_every == 0:
                    if not self.session_is_running(session.id):
                        stop_reason = "detenida desde la interfaz"
                        break
                    created = DetectionEvent.objects.filter(
                        session_id=session.id,
                        session__status=AnalysisSession.Status.RUNNING,
                    ).create(
                        session_id=session.id,
                        faces_count=faces_count,
                        processing_time_ms=result["processing_time_ms"],
                    )

                elapsed_seconds = time.monotonic() - started_at
                if max_frames > 0 and frame_number >= max_frames:
                    stop_reason = "se alcanzó el límite máximo de frames"
                    break
                if duration > 0 and elapsed_seconds >= duration:
                    stop_reason = "se alcanzó la duración máxima configurada"
                    break
                if preview_enabled and cv2.waitKey(1) & 0xFF == ord("q"):
                    stop_reason = "el usuario presionó Q"
                    break
        except Exception as exc:
            failure_message = str(exc)
        finally:
            capture.release()
            if preview_enabled:
                cv2.destroyAllWindows()
            close_old_connections()

        elapsed_seconds = time.monotonic() - started_at
        average_fps = frame_number / elapsed_seconds if elapsed_seconds > 0 else 0

        if failure_message:
            changed = self.finish_if_running(
                session.id,
                AnalysisSession.Status.FAILED,
                frame_number,
                total_faces,
                failure_message,
            )
            if changed:
                self.create_audit_log(
                    session=session,
                    action=AuditLog.Action.STOP,
                    description=(
                        f"El sistema finalizó con error la sesión de análisis "
                        f"#{session.id}. Error: {failure_message}"
                    ),
                )
                raise CommandError(f"La sesión #{session.id} falló: {failure_message}")
            self.stdout.write(
                "La sesión cambió de estado externamente; se conserva ese estado."
            )
            return

        changed = self.finish_if_running(
            session.id,
            AnalysisSession.Status.COMPLETED,
            frame_number,
            total_faces,
        )
        if changed:
            self.create_audit_log(
                session=session,
                action=AuditLog.Action.STOP,
                description=(
                    f"La sesión de análisis #{session.id} finalizó: {stop_reason or 'fin normal'}."
                ),
            )
            final_status = "completada"
        else:
            final_status = "detenida desde la interfaz"

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Sesión #{session.id} {final_status}.")
        )
        self.stdout.write(f"Frames procesados: {frame_number}")
        self.stdout.write(f"Rostros acumulados: {total_faces}")
        self.stdout.write(f"Duración real: {elapsed_seconds:.2f} segundos")
        self.stdout.write(f"FPS promedio: {average_fps:.2f}")