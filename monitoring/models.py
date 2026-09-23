from django.conf import settings
from django.db import models

from venues.models import Venue


class Incident(models.Model):
    class Severity(models.TextChoices):
        INFO = "info", "Información"
        WARNING = "warning", "Advertencia"
        ERROR = "error", "Error"
        CRITICAL = "critical", "Crítico"

    class Status(models.TextChoices):
        OPEN = "open", "Abierta"
        REVIEWED = "reviewed", "Revisada"
        RESOLVED = "resolved", "Resuelta"

    venue = models.ForeignKey(
        Venue,
        on_delete=models.CASCADE,
        related_name="incidents",
        null=True,
        blank=True,
        verbose_name="Local",
    )
    module = models.CharField(
        max_length=80,
        verbose_name="Módulo afectado",
        help_text="Ejemplo: cameras, ai_vision, reports o operations.",
    )
    title = models.CharField(
        max_length=180,
        verbose_name="Título",
    )
    description = models.TextField(
        verbose_name="Descripción",
    )
    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.WARNING,
        verbose_name="Severidad",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        verbose_name="Estado",
    )
    technical_details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Detalle técnico",
        help_text=(
            "No guardar contraseñas, tokens, URLs con credenciales "
            "ni datos personales."
        ),
    )
    occurred_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha y hora de ocurrencia",
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha y hora de revisión",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_incidents",
        verbose_name="Revisada por",
    )

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = "Incidencia"
        verbose_name_plural = "Incidencias"

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.title}"

    def mark_reviewed(self, user):
        if self.status == self.Status.OPEN:
            self.status = self.Status.REVIEWED
            self.reviewed_by = user

            from django.utils import timezone

            self.reviewed_at = timezone.now()

            self.save(
                update_fields=[
                    "status",
                    "reviewed_by",
                    "reviewed_at",
                ]
            )

    def mark_resolved(self, user):
        self.status = self.Status.RESOLVED
        self.reviewed_by = user

        from django.utils import timezone

        self.reviewed_at = timezone.now()

        self.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
            ]
        )


class AuditLog(models.Model):
    class Action(models.TextChoices):
        LOGIN = "login", "Inicio de sesión"
        LOGOUT = "logout", "Cierre de sesión"
        CREATE = "create", "Creación"
        UPDATE = "update", "Actualización"
        DELETE = "delete", "Eliminación"
        START = "start", "Inicio"
        STOP = "stop", "Detención"
        VIEW = "view", "Visualización"
        EXPORT = "export", "Exportación"
        ACCESS_DENIED = "access_denied", "Acceso denegado"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="Usuario",
    )
    venue = models.ForeignKey(
        Venue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="Local",
    )
    action = models.CharField(
        max_length=30,
        choices=Action.choices,
        verbose_name="Acción",
    )
    module = models.CharField(
        max_length=80,
        verbose_name="Módulo",
    )
    object_type = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="Tipo de objeto",
    )
    object_id = models.CharField(
        max_length=64,
        blank=True,
        verbose_name="Identificador del objeto",
    )
    description = models.CharField(
        max_length=255,
        verbose_name="Descripción",
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Dirección IP",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha y hora",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Registro de auditoría"
        verbose_name_plural = "Registros de auditoría"

    def __str__(self):
        return (
            f"{self.created_at:%d-%m-%Y %H:%M} — "
            f"{self.get_action_display()} — {self.module}"
        )