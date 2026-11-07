from django.conf import settings
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


    arrived_at = models.DateTimeField(null=True, blank=True, verbose_name="Llegada al local")
    bill_requested_at = models.DateTimeField(null=True, blank=True, verbose_name="Cuenta solicitada")

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

    class Source(models.TextChoices):
        STAFF = "staff", "Registrada por el personal"
        CUSTOMER_QR = "customer_qr", "Cliente vía QR"

    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.STAFF,
        verbose_name="Origen",
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


    value_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, choices=[(i, str(i)) for i in range(1, 6)], verbose_name="Precio-calidad")
    return_intent = models.CharField(
        max_length=10, blank=True, choices=[("yes", "Sí"), ("maybe", "Tal vez"), ("no", "No")],
        verbose_name="Intención de volver")
    cleanliness_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, choices=[(i, str(i)) for i in range(1, 6)], verbose_name="Limpieza")
    restroom_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, choices=[(i, str(i)) for i in range(1, 6)], verbose_name="Baños")
    ambience_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, choices=[(i, str(i)) for i in range(1, 6)], verbose_name="Ambiente y comodidad")

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


class WaitlistEntry(models.Model):
    """Grupo que llegó al local y espera mesa (mide el tiempo hasta la asignación)."""

    venue = models.ForeignKey("venues.Venue", on_delete=models.CASCADE, related_name="waitlist", verbose_name="Local")
    party_name = models.CharField(max_length=80, blank=True, verbose_name="Nombre (opcional)")
    guests = models.PositiveSmallIntegerField(default=2, verbose_name="Comensales")
    arrived_at = models.DateTimeField(default=timezone.now, verbose_name="Llegada")
    seated_at = models.DateTimeField(null=True, blank=True, verbose_name="Asignada a una mesa")
    cancelled = models.BooleanField(default=False, verbose_name="Se retiró sin mesa")
    service_session = models.ForeignKey("operations.ServiceSession", on_delete=models.SET_NULL, null=True,
                                        blank=True, related_name="waitlist_entries", verbose_name="Atención")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name="Registrado por")

    class Meta:
        ordering = ["arrived_at"]
        verbose_name = "Llegada en espera"
        verbose_name_plural = "Lista de espera"

    def __str__(self):
        return f"{self.party_name or 'Grupo'} ({self.guests})"

    @property
    def waiting_minutes(self):
        end = self.seated_at or timezone.now()
        return max(0, round((end - self.arrived_at).total_seconds() / 60))


class EnvironmentReading(models.Model):
    """Condiciones ambientales registradas por zona (manual; preparado para sensores)."""

    venue = models.ForeignKey("venues.Venue", on_delete=models.CASCADE, related_name="environment_readings",
                              verbose_name="Local")
    zone = models.CharField(max_length=80, default="Salón principal", verbose_name="Zona")
    lighting = models.PositiveSmallIntegerField(null=True, blank=True, choices=[(i, str(i)) for i in range(1, 6)],
                                                verbose_name="Iluminación (1 muy baja · 5 muy buena)")
    noise = models.PositiveSmallIntegerField(null=True, blank=True, choices=[(i, str(i)) for i in range(1, 6)],
                                             verbose_name="Ruido (1 muy bajo · 5 muy alto)")
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True,
                                        verbose_name="Temperatura (°C)")
    notes = models.CharField(max_length=200, blank=True, verbose_name="Notas")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    verbose_name="Registrado por")
    recorded_at = models.DateTimeField(default=timezone.now, verbose_name="Fecha")

    class Meta:
        ordering = ["-recorded_at"]
        verbose_name = "Condición ambiental"
        verbose_name_plural = "Condiciones ambientales"

    def __str__(self):
        return f"{self.zone} — {self.recorded_at:%d-%m %H:%M}"


class InfrastructureReport(models.Model):
    """Incidencia de infraestructura o servicios primarios (baños, terraza, limpieza...)."""

    class Area(models.TextChoices):
        RESTROOMS = "restrooms", "Baños"
        TERRACE = "terrace", "Terraza"
        CLEANING = "cleaning", "Limpieza"
        CLIMATE = "climate", "Climatización"
        FURNITURE = "furniture", "Mobiliario"
        OTHER = "other", "Otro"

    venue = models.ForeignKey("venues.Venue", on_delete=models.CASCADE, related_name="infrastructure_reports",
                              verbose_name="Local")
    area = models.CharField(max_length=20, choices=Area.choices, verbose_name="Área")
    description = models.CharField(max_length=255, verbose_name="Descripción")
    status = models.CharField(max_length=10, default="open", choices=[("open", "Abierta"), ("resolved", "Resuelta")],
                              verbose_name="Estado")
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    verbose_name="Reportado por")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Resuelta")

    class Meta:
        ordering = ["status", "-created_at"]
        verbose_name = "Reporte de infraestructura"
        verbose_name_plural = "Reportes de infraestructura"

    def __str__(self):
        return f"{self.get_area_display()}: {self.description}"


class Notification(models.Model):
    """Alerta para el equipo del local: atención, disconformidad, aprobación, ingresos y servicio."""

    class Kind(models.TextChoices):
        ATTENTION = "attention", "Busca atención"
        DISCOMFORT = "discomfort", "Señal de disconformidad"
        APPROVAL = "approval", "Señal de aprobación"
        ARRIVAL = "arrival", "Ingreso de comensales"
        WAITING = "waiting", "Mesa sin atención"
        READY = "ready", "Platos listos"
        BILL = "bill", "Cuenta solicitada"
        CHECKOUT = "checkout", "Experiencia en caja"
        IMPATIENCE = "impatience", "Impaciencia sostenida"

    venue = models.ForeignKey("venues.Venue", on_delete=models.CASCADE, related_name="notifications", verbose_name="Local")
    table = models.ForeignKey("operations.RestaurantTable", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="notifications", verbose_name="Mesa")
    kind = models.CharField(max_length=20, choices=Kind.choices, verbose_name="Tipo")
    level = models.CharField(max_length=10, default="info",
                             choices=[("info", "Información"), ("success", "Positiva"), ("warning", "Atención"), ("danger", "Urgente")],
                             verbose_name="Nivel")
    title = models.CharField(max_length=120, verbose_name="Título")
    message = models.CharField(max_length=255, blank=True, verbose_name="Detalle")
    dedupe_key = models.CharField(max_length=120, db_index=True, verbose_name="Clave de duplicado")
    created_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name="Fecha")
    acknowledged_at = models.DateTimeField(null=True, blank=True, verbose_name="Atendida")
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                        verbose_name="Atendida por")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"

    def __str__(self):
        return self.title


class AlertSettings(models.Model):
    """Umbrales de alerta de cada local (configurables en el Centro de gestión)."""

    venue = models.OneToOneField("venues.Venue", on_delete=models.CASCADE, related_name="alert_settings", verbose_name="Local")
    impatience_pct = models.PositiveSmallIntegerField(default=70, verbose_name="Umbral de impaciencia (%)",
                                                      help_text="Índice = 60% búsqueda de atención + 40% (100 − IEO).")
    impatience_minutes = models.PositiveSmallIntegerField(default=8, verbose_name="Minutos sostenidos de impaciencia")
    discomfort_ieo = models.PositiveSmallIntegerField(default=45, verbose_name="IEO bajo (disconformidad)")
    discomfort_minutes = models.PositiveSmallIntegerField(default=0, verbose_name="Minutos sostenidos de IEO bajo",
                                                          help_text="0 = aviso inmediato.")
    waiting_minutes = models.PositiveSmallIntegerField(default=20, verbose_name="Minutos sin atención")
    approval_ieo = models.PositiveSmallIntegerField(default=80, verbose_name="IEO de aprobación")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de alertas"
        verbose_name_plural = "Configuraciones de alertas"

    def __str__(self):
        return f"Alertas de {self.venue}"
