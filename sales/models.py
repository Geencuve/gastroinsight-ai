from decimal import Decimal

from django.conf import settings
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import models
from django.db.models import F, Q, Sum
from django.utils import timezone

from menus.models import Dish
from operations.models import ServiceSession


class Order(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Abierto"
        CONFIRMED = "CONFIRMED", "Confirmado"
        PAID = "PAID", "Pagado"
        CANCELLED = "CANCELLED", "Anulado"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Efectivo"
        DEBIT = "DEBIT", "Tarjeta de débito"
        CREDIT = "CREDIT", "Tarjeta de crédito"
        TRANSFER = "TRANSFER", "Transferencia"
        OTHER = "OTHER", "Otro"

    service_session = models.ForeignKey(
        ServiceSession,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="Sesión de atención",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
        verbose_name="Estado",
    )

    opened_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de apertura",
    )

    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de confirmación",
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de pago",
    )

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de anulación",
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        blank=True,
        verbose_name="Medio de pago",
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Subtotal",
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Descuento",
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Total",
    )

    notes = models.TextField(
        blank=True,
        verbose_name="Observaciones",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_orders",
        verbose_name="Creado por",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización",
    )

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ("-opened_at",)
        indexes = [
            models.Index(
                fields=("status", "-opened_at"),
                name="sales_order_status_opened_idx",
            ),
            models.Index(
                fields=("service_session", "status"),
                name="sales_order_session_status_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(subtotal__gte=0),
                name="sales_order_subtotal_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(discount_amount__gte=0),
                name="sales_order_discount_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(total__gte=0),
                name="sales_order_total_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(discount_amount__lte=F("subtotal")),
                name="sales_order_discount_lte_subtotal",
            ),
        ]

    def __str__(self):
        return (
            f"Pedido #{self.id} — "
            f"{self.service_session.table.code}"
        )

    @property
    def can_be_edited(self):
        return self.status == self.Status.OPEN

    def clean(self):
        errors = {}

        if self.service_session_id:
            if self.service_session.status == ServiceSession.Status.CLOSED:
                errors[NON_FIELD_ERRORS] = (
                    "No puedes crear o modificar pedidos "
                    "en una sesión cerrada."
                )

        if self.discount_amount > self.subtotal:
            errors["discount_amount"] = (
                "El descuento no puede ser mayor al subtotal."
            )

        if errors:
            raise ValidationError(errors)

    def recalculate_totals(self, save=True):
        values = self.items.aggregate(
            calculated_subtotal=Sum("line_total")
        )

        subtotal = values["calculated_subtotal"] or Decimal("0.00")

        # Si se eliminan ítems, el descuento no puede superar el nuevo subtotal.
        if self.discount_amount > subtotal:
            self.discount_amount = subtotal

        total = max(
            Decimal("0.00"),
            subtotal - self.discount_amount,
        )

        self.subtotal = subtotal
        self.total = total

        if save:
            self.save(
                update_fields=(
                    "subtotal",
                    "discount_amount",
                    "total",
                    "updated_at",
                )
            )

        return self.total

    def confirm(self):
        if self.status != self.Status.OPEN:
            raise ValidationError(
                "Solo se pueden confirmar pedidos abiertos."
            )

        if not self.items.exists():
            raise ValidationError(
                "No puedes confirmar un pedido sin ítems."
            )

        self.recalculate_totals(save=False)

        self.status = self.Status.CONFIRMED
        self.confirmed_at = timezone.now()

        self.full_clean()
        self.save(
            update_fields=(
                "status",
                "confirmed_at",
                "subtotal",
                "total",
                "updated_at",
            )
        )

    def mark_as_paid(self, payment_method):
        if self.status != self.Status.CONFIRMED:
            raise ValidationError(
                "Solo se pueden pagar pedidos confirmados."
            )

        if payment_method not in self.PaymentMethod.values:
            raise ValidationError(
                "Selecciona un medio de pago válido."
            )

        self.status = self.Status.PAID
        self.payment_method = payment_method
        self.paid_at = timezone.now()

        self.full_clean()
        self.save(
            update_fields=(
                "status",
                "payment_method",
                "paid_at",
                "updated_at",
            )
        )

    def cancel(self):
        if self.status == self.Status.PAID:
            raise ValidationError(
                "No puedes anular un pedido que ya fue pagado."
            )

        if self.status == self.Status.CANCELLED:
            raise ValidationError(
                "El pedido ya se encuentra anulado."
            )

        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()

        self.save(
            update_fields=(
                "status",
                "cancelled_at",
                "updated_at",
            )
        )


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Pedido",
    )

    dish = models.ForeignKey(
        Dish,
        on_delete=models.PROTECT,
        related_name="order_items",
        verbose_name="Plato",
    )

    dish_name = models.CharField(
        max_length=180,
        editable=False,
        verbose_name="Nombre histórico del plato",
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
        verbose_name="Precio unitario histórico",
    )

    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name="Cantidad",
    )

    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
        verbose_name="Total de línea",
    )

    notes = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Observaciones",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de registro",
    )


    prep_status = models.CharField(
        max_length=12, default="pending", verbose_name="Estado de preparación",
        choices=[("pending", "Pendiente"), ("preparing", "En preparación"), ("ready", "Listo"), ("delivered", "Entregado")],
    )
    prep_started_at = models.DateTimeField(null=True, blank=True, verbose_name="Inicio de preparación")
    ready_at = models.DateTimeField(null=True, blank=True, verbose_name="Listo para servir")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Entregado")

    class Meta:
        verbose_name = "Ítem de pedido"
        verbose_name_plural = "Ítems de pedido"
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("order", "dish"),
                name="sales_unique_dish_per_order",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="sales_order_item_quantity_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="sales_order_item_unit_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(line_total__gte=0),
                name="sales_order_item_line_total_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.quantity} × {self.dish_name}"

    def clean(self):
        errors = {}

        if self.order_id and not self.order.can_be_edited:
            errors[NON_FIELD_ERRORS] = (
                "Solo puedes modificar los ítems de un pedido abierto."
            )

        if self.dish_id:
            menu = self.dish.menu

            if menu.venue_id != self.order.service_session.table.venue_id:
                errors["dish"] = (
                    "El plato debe pertenecer al mismo local "
                    "que la sesión de atención."
                )

            if not menu.is_active or not self.dish.is_available:
                errors["dish"] = (
                    "El plato seleccionado no se encuentra disponible."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.dish_name = self.dish.name
            self.unit_price = self.dish.price

        self.line_total = self.unit_price * self.quantity

        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        order = self.order
        super().delete(*args, **kwargs)
        order.recalculate_totals()

    def refresh_order_total(self):
        self.order.recalculate_totals()