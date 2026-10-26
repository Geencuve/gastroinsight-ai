from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.core.validators import MaxValueValidator, MinValueValidator
from menus.models import Dish
from venues.models import Venue
from django.core.exceptions import ValidationError

class RestaurantTable(models.Model):
    venue = models.ForeignKey(
        Venue,
        on_delete=models.CASCADE,
        related_name="tables",
        verbose_name="Local",
    )
    code = models.CharField(
        max_length=30,
        verbose_name="Código o número de mesa",
        help_text="Ejemplo: M01, Terraza-2 o Mesa 10.",
    )
    capacity = models.PositiveIntegerField(
        default=4,
        verbose_name="Capacidad",
        help_text="Cantidad máxima estimada de personas.",
    )
    zone_name = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Zona",
        help_text="Ejemplo: Salón principal, terraza o barra.",
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
        ordering = ["venue__name", "code"]
        verbose_name = "Mesa"
        verbose_name_plural = "Mesas"
        constraints = [
            models.UniqueConstraint(
                fields=["venue", "code"],
                name="unique_table_code_per_venue",
            ),
            models.CheckConstraint(
                check=Q(capacity__gte=1),
                name="table_capacity_must_be_positive",
            ),
        ]

    def __str__(self):
        return f"{self.venue.name} — {self.code}"


class ServiceSession(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Abierta"
        CLOSED = "closed", "Cerrada"
        CANCELLED = "cancelled", "Cancelada"

    table = models.ForeignKey(
        RestaurantTable,
        on_delete=models.PROTECT,
        related_name="service_sessions",
        verbose_name="Mesa",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        verbose_name="Estado",
    )
    started_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha y hora de inicio",
    )
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha y hora de cierre",
    )
    guests_count = models.PositiveIntegerField(
        default=1,
        verbose_name="Cantidad estimada de comensales",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Observaciones",
    )
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_service_sessions",
        verbose_name="Creada por",
    )
    closed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_service_sessions",
        verbose_name="Cerrada por",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Sesión de atención"
        verbose_name_plural = "Sesiones de atención"
        constraints = [
            models.UniqueConstraint(
                fields=["table"],
                condition=Q(status="open"),
                name="only_one_open_service_session_per_table",
            ),
            models.CheckConstraint(
                check=Q(guests_count__gte=1),
                name="service_session_guests_must_be_positive",
            ),
        ]

    def __str__(self):
        return (
            f"Sesión #{self.id} — {self.table.code} — "
            f"{self.get_status_display()}"
        )

    @property
    def venue(self):
        return self.table.venue

    PENDING_ORDER_STATUSES = ("OPEN", "CONFIRMED")

    def pending_orders_count(self):
        return self.orders.filter(
            status__in=self.PENDING_ORDER_STATUSES
        ).count()

    def ensure_no_pending_orders(self, action="cerrar"):
        pending = self.pending_orders_count()
        if pending:
            plural = "s" if pending != 1 else ""
            raise ValidationError(
                f"No puedes {action} la mesa {self.table.code}: "
                f"tiene {pending} pedido{plural} sin pagar. "
                f"Págalos o anúlalos primero."
            )

    def close(self, user=None):
        if self.status != self.Status.OPEN:
            return False

        self.ensure_no_pending_orders("cerrar")

        self.status = self.Status.CLOSED
        self.ended_at = timezone.now()
        self.closed_by = user
        self.save(
            update_fields=[
                "status",
                "ended_at",
                "closed_by",
                "updated_at",
            ]
        )
        return True

    def cancel(self, user=None):
        if self.status != self.Status.OPEN:
            return False

        self.ensure_no_pending_orders("cancelar")

        self.status = self.Status.CANCELLED
        self.ended_at = timezone.now()
        self.closed_by = user
        self.save(
            update_fields=[
                "status",
                "ended_at",
                "closed_by",
                "updated_at",
            ]
        )
        return True

class SatisfactionEvaluation(models.Model):
    class Rating(models.IntegerChoices):
        VERY_DISSATISFIED = 1, "Muy insatisfecho"
        DISSATISFIED = 2, "Insatisfecho"
        NEUTRAL = 3, "Neutral"
        SATISFIED = 4, "Satisfecho"
        VERY_SATISFIED = 5, "Muy satisfecho"

    service_session = models.ForeignKey(
        ServiceSession,
        on_delete=models.PROTECT,
        related_name="evaluations",
        verbose_name="Sesión de atención",
    )
    dish = models.ForeignKey(
        Dish,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="satisfaction_evaluations",
        verbose_name="Plato asociado",
        help_text="Opcional: producto evaluado durante la atención.",
    )
    rating = models.PositiveSmallIntegerField(
        choices=Rating.choices,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ],
        verbose_name="Valoración",
    )
    comment = models.TextField(
        blank=True,
        max_length=500,
        verbose_name="Comentario voluntario",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha y hora de registro",
    )
    registered_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="registered_satisfaction_evaluations",
        verbose_name="Registrada por",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Evaluación voluntaria"
        verbose_name_plural = "Evaluaciones voluntarias"
        constraints = [
            models.CheckConstraint(
                check=models.Q(rating__gte=1, rating__lte=5),
                name="satisfaction_rating_between_1_and_5",
            )
        ]

    def __str__(self):
        return (
            f"Evaluación #{self.id} — "
            f"{self.get_rating_display()} — "
            f"Sesión #{self.service_session_id}"
        )

    @property
    def venue(self):
        return self.service_session.table.venue

    def clean(self):
        super().clean()

        if self.dish_id and self.service_session_id:
            session_venue_id = self.service_session.table.venue_id
            dish_venue_id = self.dish.menu.venue_id

            if session_venue_id != dish_venue_id:
                raise ValidationError(
                    {
                        "dish": (
                            "El plato seleccionado debe pertenecer al "
                            "mismo local que la sesión de atención."
                        )
                    }
                )