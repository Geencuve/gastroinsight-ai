from django.conf import settings
from django.db import models
from django.utils import timezone

from cameras.models import Camera


class AnalysisSession(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        RUNNING = "running", "En ejecución"
        COMPLETED = "completed", "Completada"
        FAILED = "failed", "Fallida"
        STOPPED = "stopped", "Detenida"

    camera = models.ForeignKey(
        Camera,
        on_delete=models.CASCADE,
        related_name="analysis_sessions",
        verbose_name="Cámara",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Estado",
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Inicio",
    )
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Término",
    )
    frames_processed = models.PositiveIntegerField(
        default=0,
        verbose_name="Frames procesados",
    )
    total_faces_detected = models.PositiveIntegerField(
        default=0,
        verbose_name="Rostros detectados",
    )
    error_message = models.TextField(
        blank=True,
        verbose_name="Mensaje de error",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Sesión de análisis"
        verbose_name_plural = "Sesiones de análisis"

    def __str__(self):
        return f"Sesión #{self.pk} — {self.camera.name} — {self.get_status_display()}"

    def start(self):
        self.status = self.Status.RUNNING
        self.started_at = timezone.now()
        self.error_message = ""
        self.save(
            update_fields=[
                "status",
                "started_at",
                "error_message",
            ]
        )

    def finish(self, status=Status.COMPLETED, error_message=""):
        self.status = status
        self.ended_at = timezone.now()
        self.error_message = error_message
        self.save(
            update_fields=[
                "status",
                "ended_at",
                "error_message",
                "frames_processed",
                "total_faces_detected",
            ]
        )


class DetectionEvent(models.Model):
    class Emotion(models.TextChoices):
        UNKNOWN = "unknown", "Sin estimación"
        NEUTRAL = "neutral", "Neutral"
        HAPPY = "happy", "Positiva / feliz"
        SAD = "sad", "Negativa / triste"
        SURPRISED = "surprised", "Sorpresa"
        ANGRY = "angry", "Enojo"
        DISGUST = "disgust", "Disgusto"
        FEAR = "fear", "Miedo"
        CONTEMPT = "contempt", "Desprecio"

    session = models.ForeignKey(
        AnalysisSession,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name="Sesión de análisis",
    )
    detected_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha y hora de detección",
    )
    faces_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Cantidad de rostros",
    )
    estimated_emotion = models.CharField(
        max_length=20,
        choices=Emotion.choices,
        default=Emotion.UNKNOWN,
        verbose_name="Emoción estimada",
    )
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Confianza",
        help_text="Valor entre 0 y 1, si existe un modelo que lo entregue.",
    )
    processing_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Tiempo de procesamiento (ms)",
    )
    detector_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Confianza del detector",
    )
    occupancy = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name="Ocupación (personas visibles, mediana)",
    )
    presence_ratio = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
        verbose_name="Proporción del tiempo con presencia",
    )
    activity_level = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name="Nivel de actividad (0-100)",
    )
    emotion_distribution = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Distribución de expresiones",
        help_text="Conteo agregado de expresiones en la ventana de fotogramas.",
    )
    table = models.ForeignKey(
        "operations.RestaurantTable",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="detection_events",
        verbose_name="Mesa asociada",
    )
    service_session = models.ForeignKey(
        "operations.ServiceSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="detection_events",
        verbose_name="Sesión de atención asociada",
    )

    class Meta:
        ordering = ["-detected_at"]
        verbose_name = "Evento de detección"
        verbose_name_plural = "Eventos de detección"

    def __str__(self):
        return (
            f"Sesión #{self.session_id} — "
            f"{self.faces_count} rostro(s) — "
            f"{self.detected_at:%d-%m-%Y %H:%M:%S}"
        )