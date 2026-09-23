from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from venues.models import Venue


class PrivacyPolicy(models.Model):
    venue = models.OneToOneField(
        Venue,
        on_delete=models.CASCADE,
        related_name="privacy_policy",
        verbose_name="Local",
    )
    version = models.CharField(
        max_length=40,
        default="1.0",
        verbose_name="Versión de política",
    )
    purpose = models.TextField(
        verbose_name="Finalidad del procesamiento",
        help_text=(
            "Ejemplo: generar indicadores agregados de ocupación "
            "y funcionamiento operacional; no identificar personas."
        ),
    )
    processing_enabled = models.BooleanField(
        default=False,
        verbose_name="Procesamiento visual habilitado",
        help_text=(
            "Solo debe habilitarse cuando exista autorización "
            "y se cumplan las condiciones definidas."
        ),
    )
    retain_aggregated_events_days = models.PositiveIntegerField(
        default=30,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(365),
        ],
        verbose_name="Retención de eventos agregados (días)",
    )
    retain_incidents_days = models.PositiveIntegerField(
        default=90,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(730),
        ],
        verbose_name="Retención de incidencias (días)",
    )
    store_original_images = models.BooleanField(
        default=False,
        verbose_name="Guardar imágenes originales",
        help_text=(
            "Debe permanecer desactivado en el MVP. "
            "El prototipo solo conserva métricas agregadas."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_privacy_policies",
        verbose_name="Actualizada por",
    )

    class Meta:
        verbose_name = "Política de privacidad"
        verbose_name_plural = "Políticas de privacidad"

    def __str__(self):
        return (
            f"{self.venue.name} — Política v{self.version}"
        )

    @property
    def is_processing_authorized(self):
        if not self.processing_enabled:
            return False

        if self.store_original_images:
            return False

        return any(
            authorization.is_valid
            for authorization in self.authorizations.all()
        )


class ProcessingAuthorization(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Vigente"
        REVOKED = "revoked", "Revocada"
        EXPIRED = "expired", "Vencida"

    privacy_policy = models.ForeignKey(
        PrivacyPolicy,
        on_delete=models.CASCADE,
        related_name="authorizations",
        verbose_name="Política de privacidad",
    )
    source_description = models.CharField(
        max_length=255,
        verbose_name="Fuente o alcance autorizado",
        help_text=(
            "Ejemplo: Webcam de desarrollo ubicada en salón principal."
        ),
    )
    authorization_type = models.CharField(
        max_length=120,
        default="Autorización interna del establecimiento",
        verbose_name="Tipo de autorización",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="Estado",
    )
    accepted_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha de aceptación",
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de vencimiento",
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_processing_authorizations",
        verbose_name="Registrada por",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Observaciones",
    )

    class Meta:
        ordering = ["-accepted_at"]
        verbose_name = "Autorización de procesamiento"
        verbose_name_plural = "Autorizaciones de procesamiento"

    def __str__(self):
        return (
            f"{self.privacy_policy.venue.name} — "
            f"{self.get_status_display()} — "
            f"{self.source_description}"
        )

    @property
    def is_valid(self):
        if self.status != self.Status.ACTIVE:
            return False

        if self.expires_at and self.expires_at <= timezone.now():
            return False

        return True