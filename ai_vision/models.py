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
    valence = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
        verbose_name="Valencia de las expresiones (-1 a 1)",
    )
    attention_seeking = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
        verbose_name="Proporción de rostros buscando atención",
    )
    experience_index = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name="Índice de Experiencia Observable (0-100)",
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


TRAINING_EXPRESSION_LABELS = [
    ("neutral", "Neutral"), ("happy", "Alegría"), ("surprised", "Sorpresa"), ("sad", "Tristeza"),
    ("angry", "Enojo"), ("disgust", "Disgusto"), ("fear", "Miedo"), ("contempt", "Desprecio"),
]
TRAINING_ATTENTION_LABELS = [("attentive", "Mirando la mesa"), ("seeking", "Buscando atención")]


class TrainingSample(models.Model):
    """Muestra etiquetada con consentimiento. Solo guarda el recorte del rostro (128x128, gris)."""

    class Kind(models.TextChoices):
        EXPRESSION = "expression", "Expresión facial"
        ATTENTION = "attention", "Búsqueda de atención"

    kind = models.CharField(max_length=20, choices=Kind.choices, verbose_name="Tipo de dato")
    label = models.CharField(
        max_length=20, choices=TRAINING_EXPRESSION_LABELS + TRAINING_ATTENTION_LABELS, verbose_name="Etiqueta real",
    )
    image = models.ImageField(upload_to="training/%Y/%m/", blank=True, verbose_name="Recorte del rostro")
    probabilities = models.JSONField(default=list, blank=True, verbose_name="Probabilidades FER+")
    predicted_label = models.CharField(max_length=20, blank=True, verbose_name="Predicción del modelo base")
    predicted_confidence = models.FloatField(null=True, blank=True, verbose_name="Confianza de la predicción")
    detector_score = models.FloatField(null=True, blank=True, verbose_name="Confianza del detector")
    yaw = models.FloatField(null=True, blank=True, verbose_name="Giro de la cabeza")
    consent_confirmed = models.BooleanField(default=False, verbose_name="Consentimiento confirmado")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="training_samples", verbose_name="Cargada por",
    )
    venue = models.ForeignKey("venues.Venue", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Local")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de carga")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Muestra de entrenamiento"
        verbose_name_plural = "Muestras de entrenamiento"

    def __str__(self):
        return f"Muestra #{self.pk} — {self.get_label_display()}"

    def delete(self, *args, **kwargs):
        if self.image:
            self.image.delete(save=False)
        return super().delete(*args, **kwargs)


class CalibrationModel(models.Model):
    """Calibración entrenada sobre las muestras etiquetadas."""

    kind = models.CharField(max_length=20, choices=TrainingSample.Kind.choices, verbose_name="Tipo")
    active = models.BooleanField(default=False, verbose_name="Activa")
    samples_count = models.PositiveIntegerField(default=0, verbose_name="Muestras usadas")
    accuracy_before = models.FloatField(null=True, blank=True, verbose_name="Precisión del modelo base (%)")
    accuracy_after = models.FloatField(null=True, blank=True, verbose_name="Precisión calibrada (%)")
    weights = models.JSONField(default=dict, blank=True, verbose_name="Parámetros")
    labels = models.JSONField(default=list, blank=True, verbose_name="Etiquetas")
    confusion_before = models.JSONField(default=dict, blank=True)
    confusion_after = models.JSONField(default=dict, blank=True)
    notes = models.CharField(max_length=255, blank=True, verbose_name="Notas")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Creada por",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Calibración del modelo"
        verbose_name_plural = "Calibraciones del modelo"

    def __str__(self):
        return f"{self.get_kind_display()} — {self.created_at:%d-%m-%Y %H:%M}"
