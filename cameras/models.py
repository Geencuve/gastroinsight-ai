from django.db import models

from venues.models import Venue


class Camera(models.Model):
    class SourceType(models.TextChoices):
        WEBCAM = "webcam", "Webcam local"
        IP_CAMERA = "ip_camera", "Cámara IP / RTSP"
        VIDEO_FILE = "video_file", "Archivo de video"
        DEMO = "demo", "Demostración"

    venue = models.ForeignKey(
        Venue,
        on_delete=models.CASCADE,
        related_name="cameras",
        verbose_name="Local",
    )
    name = models.CharField(
        max_length=120,
        verbose_name="Nombre de la cámara",
    )
    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.WEBCAM,
        verbose_name="Tipo de fuente",
    )
    source = models.CharField(
        max_length=500,
        default="0",
        help_text=(
            "Webcam: 0. Cámara IP: URL RTSP/HTTP. "
            "Video: ruta relativa o absoluta del archivo."
        ),
        verbose_name="Origen",
    )
    table = models.ForeignKey(
        "operations.RestaurantTable",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cameras",
        verbose_name="Mesa monitoreada",
        help_text="Mesa que cubre esta cámara; permite asociar eventos a sesiones de atención.",
    )
    zone_name = models.CharField(
        max_length=120,
        blank=True,
        help_text="Ejemplo: Salón principal, Terraza o Mesa 1.",
        verbose_name="Zona monitoreada",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activa",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Observaciones",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["venue__name", "name"]
        verbose_name = "Cámara"
        verbose_name_plural = "Cámaras"
        constraints = [
            models.UniqueConstraint(
                fields=["venue", "name"],
                name="unique_camera_name_per_venue",
            )
        ]

    def __str__(self):
        return f"{self.name} — {self.venue.name}"
