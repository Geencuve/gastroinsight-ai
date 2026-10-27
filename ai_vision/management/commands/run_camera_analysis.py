import time
from decimal import Decimal

import cv2
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from ai_vision.services.association import find_service_session
from ai_vision.services.vision_pipeline import EventWindow, ModelsNotAvailable, VisionPipeline
from cameras.models import Camera
from monitoring.models import AuditLog
from privacy.models import PrivacyPolicy

# Etiquetas sin tildes: cv2.putText no dibuja caracteres acentuados.
PREVIEW_LABELS = {
    "neutral": "neutral", "happy": "alegria", "sad": "tristeza", "surprised": "sorpresa",
    "angry": "enojo", "disgust": "disgusto", "fear": "miedo", "contempt": "desprecio",
}


def to_decimal(value):
    return None if value is None else Decimal(str(round(value, 4)))


class Command(BaseCommand):
    help = (
        "Ejecuta el análisis visual no biométrico (YuNet + FER+) para una sesión "
        "pendiente creada desde la interfaz. Presiona Q en la ventana para detener."
    )

    def add_arguments(self, parser):
        parser.add_argument("session_id", type=int, help="ID de la sesión pendiente.")
        parser.add_argument("--sample-every", type=int, default=15,
                            help="Guardar un evento agregado cada N fotogramas. Por defecto: 15.")
        parser.add_argument("--max-frames", type=int, default=0,
                            help="Detener tras N fotogramas; 0 = sin límite.")
        parser.add_argument("--duration", type=int, default=0,
                            help="Duración máxima en segundos; 0 = sin límite.")
        parser.add_argument("--threshold", type=float, default=0.70,
                            help="Confianza mínima del detector de rostros. Por defecto: 0.70.")
        parser.add_argument("--fer-every", type=int, default=2,
                            help="Clasificar expresiones cada N fotogramas (la detección es en todos). Por defecto: 2.")
        parser.add_argument("--max-width", type=int, default=640,
                            help="Ancho máximo para la detección; 0 = tamaño original. Por defecto: 640.")
        parser.add_argument("--check-every-seconds", type=float, default=1.0,
                            help="Cada cuántos segundos verificar estado, cámara y privacidad. Por defecto: 1.")
        parser.add_argument("--no-preview", action="store_true",
                            help="Ejecutar sin abrir una ventana de OpenCV.")

    def get_capture_source(self, camera):
        source = camera.source
        if source is None or not str(source).strip():
            raise CommandError("La cámara no tiene un origen configurado.")
        source = str(source).strip()
        if camera.source_type == Camera.SourceType.WEBCAM:
            if not source.isdigit():
                raise CommandError("Una webcam debe tener un origen numérico, por ejemplo: 0.")
            return int(source)
        return source

    def create_audit_log(self, session, action, description):
        return AuditLog.objects.create(
            user=None, venue=session.camera.venue, action=action, module="ai_vision",
            object_type="AnalysisSession", object_id=str(session.id), description=description,
        )

    def session_is_running(self, session_id):
        return AnalysisSession.objects.filter(
            pk=session_id, status=AnalysisSession.Status.RUNNING,
        ).exists()

    def policy_is_authorized(self, venue_id):
        try:
            policy = PrivacyPolicy.objects.get(venue_id=venue_id)
        except PrivacyPolicy.DoesNotExist:
            return False
        return policy.is_processing_authorized

    def finish_if_running(self, session_id, status, frame_number, total_faces, error_message=""):
        """Finaliza solo si nadie (por ejemplo, stop_session) ya cambió el estado."""
        return AnalysisSession.objects.filter(
            pk=session_id, status=AnalysisSession.Status.RUNNING,
        ).update(
            status=status, ended_at=timezone.now(), error_message=error_message,
            frames_processed=frame_number, total_faces_detected=total_faces,
        )

    def save_event(self, session, camera, window):
        summary = window.summary()
        now = timezone.now()
        DetectionEvent.objects.create(
            session_id=session.id,
            detected_at=now,
            faces_count=summary["faces_count"],
            estimated_emotion=summary["estimated_emotion"],
            confidence=to_decimal(summary["confidence"]),
            detector_confidence=to_decimal(summary["detector_confidence"]),
            emotion_distribution=summary["emotion_distribution"],
            processing_time_ms=summary["processing_time_ms"],
            occupancy=to_decimal(summary["occupancy"]),
            presence_ratio=to_decimal(summary["presence_ratio"]),
            activity_level=to_decimal(summary["activity_level"]),
            table=camera.table,
            service_session=find_service_session(camera.table, now),
        )
        return summary

    def handle(self, *args, **options):
        session_id = options["session_id"]
        sample_every = max(1, options["sample_every"])
        max_frames = max(0, options["max_frames"])
        duration = max(0, options["duration"])
        check_every = max(0.0, options["check_every_seconds"])
        fer_every = max(1, options["fer_every"])
        preview_enabled = not options["no_preview"]

        try:
            session = AnalysisSession.objects.select_related(
                "camera", "camera__venue", "camera__table",
            ).get(pk=session_id)
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

        try:
            pipeline = VisionPipeline(score_threshold=options["threshold"], max_width=max(0, options["max_width"]))
        except ModelsNotAvailable as exc:
            raise CommandError(str(exc)) from exc

        source = self.get_capture_source(camera)
        if camera.source_type == Camera.SourceType.WEBCAM:
            capture = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        else:
            capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            capture.release()
            raise CommandError(f"No se pudo abrir la fuente configurada: {camera.source}")

        claimed = AnalysisSession.objects.filter(
            pk=session.pk, status=AnalysisSession.Status.PENDING,
        ).update(
            status=AnalysisSession.Status.RUNNING, started_at=timezone.now(), ended_at=None,
            error_message="", frames_processed=0, total_faces_detected=0,
        )
        if not claimed:
            capture.release()
            raise CommandError("La sesión dejó de estar pendiente antes de iniciar.")

        session.refresh_from_db()
        self.create_audit_log(
            session=session, action=AuditLog.Action.START,
            description=f"El sistema inició el procesamiento técnico de la sesión de análisis #{session.id}.",
        )
        mesa = camera.table.code if camera.table else "sin mesa asignada"
        self.stdout.write(self.style.SUCCESS(f"Sesión #{session.id} iniciada para: {camera.name} ({mesa})"))
        self.stdout.write(
            f"Fuente: {camera.source} | Evento agregado cada {sample_every} fotogramas | "
            f"Umbral detector: {options['threshold']:.2f} | Controles cada {check_every:.1f} s"
        )

        window = EventWindow()
        frame_number = 0
        total_faces = 0
        events_saved = 0
        timing = {"lectura": 0.0, "analisis": 0.0, "controles": 0.0}
        started_at = time.monotonic()
        last_check = None
        stop_reason = ""
        failure_message = ""

        try:
            while True:
                # Controles de estado, cámara y privacidad: una vez por intervalo, no en cada fotograma.
                now_monotonic = time.monotonic()
                if last_check is None or now_monotonic - last_check >= check_every:
                    t0 = time.perf_counter()
                    close_old_connections()
                    running = self.session_is_running(session.id)
                    camera.refresh_from_db(fields=["is_active"])
                    authorized = self.policy_is_authorized(camera.venue_id)
                    timing["controles"] += time.perf_counter() - t0
                    last_check = now_monotonic
                    if not running:
                        stop_reason = "detenida desde la interfaz"
                        break
                    if not camera.is_active:
                        failure_message = "Procesamiento detenido: la cámara fue desactivada."
                        break
                    if not authorized:
                        failure_message = "Procesamiento detenido: la autorización visual ya no está vigente."
                        break

                t0 = time.perf_counter()
                success, frame = capture.read()
                timing["lectura"] += time.perf_counter() - t0
                if not success:
                    failure_message = "No fue posible leer un fotograma de la cámara."
                    break

                frame_number += 1
                t0 = time.perf_counter()
                result = pipeline.analyze(frame, classify=(frame_number % fer_every == 0))
                timing["analisis"] += time.perf_counter() - t0
                total_faces += result["faces_count"]
                window.add(result)

                if preview_enabled:
                    for face in result["faces"]:
                        box = face["box"]
                        x, y = box["x"], box["y"]
                        cv2.rectangle(frame, (x, y), (x + box["width"], y + box["height"]), (0, 200, 0), 2)
                        label = PREVIEW_LABELS.get(face["emotion"], face["emotion"])
                        cv2.putText(frame, (f"{label} {face['emotion_confidence']:.2f}" if face["emotion"] else "rostro"), (x, max(18, y - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)
                    cv2.putText(frame, f"Rostros: {result['faces_count']} | {result['processing_time_ms']} ms | "
                                       f"eventos: {events_saved}", (15, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                    cv2.imshow("GastroInsight AI - Analisis (Q para detener)", frame)
                del frame  # el fotograma se descarta inmediatamente

                if frame_number % sample_every == 0:
                    if not self.session_is_running(session.id):
                        stop_reason = "detenida desde la interfaz"
                        break
                    self.save_event(session, camera, window)
                    events_saved += 1
                    window.reset()

                elapsed_seconds = time.monotonic() - started_at
                if max_frames > 0 and frame_number >= max_frames:
                    stop_reason = "se alcanzó el límite máximo de fotogramas"
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

        # Guardar la ventana final incompleta para no perder detecciones.
        if window.frames and not failure_message and self.session_is_running(session.id):
            self.save_event(session, camera, window)
            events_saved += 1

        elapsed_seconds = time.monotonic() - started_at
        average_fps = frame_number / elapsed_seconds if elapsed_seconds > 0 else 0

        if failure_message:
            changed = self.finish_if_running(
                session.id, AnalysisSession.Status.FAILED, frame_number, total_faces, failure_message,
            )
            if changed:
                self.create_audit_log(
                    session=session, action=AuditLog.Action.STOP,
                    description=f"El sistema finalizó con error la sesión #{session.id}. Error: {failure_message}",
                )
                raise CommandError(f"La sesión #{session.id} falló: {failure_message}")
            self.stdout.write("La sesión cambió de estado externamente; se conserva ese estado.")
            return

        changed = self.finish_if_running(
            session.id, AnalysisSession.Status.COMPLETED, frame_number, total_faces,
        )
        if changed:
            self.create_audit_log(
                session=session, action=AuditLog.Action.STOP,
                description=f"La sesión de análisis #{session.id} finalizó: {stop_reason or 'fin normal'}.",
            )
            final_status = "completada"
        else:
            final_status = "detenida desde la interfaz"

        per_frame = {k: (v * 1000 / frame_number if frame_number else 0) for k, v in timing.items()}
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Sesión #{session.id} {final_status}."))
        self.stdout.write(f"Fotogramas procesados: {frame_number}")
        self.stdout.write(f"Rostros acumulados: {total_faces}")
        self.stdout.write(f"Eventos agregados guardados: {events_saved}")
        self.stdout.write(f"Duración real: {elapsed_seconds:.2f} s | FPS promedio: {average_fps:.2f}")
        self.stdout.write(
            "Tiempo promedio por fotograma: "
            f"lectura {per_frame['lectura']:.1f} ms | análisis {per_frame['analisis']:.1f} ms | "
            f"controles {per_frame['controles']:.1f} ms"
        )
