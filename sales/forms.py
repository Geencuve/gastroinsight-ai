from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from menus.models import Dish

from .models import Order, OrderItem


class OrderCreateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = (
            "service_session",
            "notes",
        )
        widgets = {
            "notes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": (
                        "Ej.: pedido inicial, alergias, "
                        "observaciones del cliente."
                    ),
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        queryset = Order.service_session.field.related_model.objects.filter(
            status="open",  # ServiceSession usa valores en minúscula
            table__is_active=True,
        ).select_related(
            "table",
            "table__venue",
        )

        if user is not None:
            from authentication.permissions import get_or_create_profile

            profile = get_or_create_profile(user)

            if not profile.is_platform_admin:
                queryset = queryset.filter(
                    table__venue__in=profile.venues.all()
                )

        self.fields["service_session"].queryset = queryset.order_by(
            "table__venue__name",
            "table__code",
        )

        self.fields["service_session"].label = (
            "Sesión de atención abierta"
        )

        self.fields["notes"].label = "Observaciones"


class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = (
            "dish",
            "quantity",
            "notes",
        )
        widgets = {
            "quantity": forms.NumberInput(
                attrs={
                    "min": 1,
                    "step": 1,
                }
            ),
            "notes": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Ej.: sin cebolla, término medio."
                    ),
                }
            ),
        }

    def __init__(self, *args, order=None, **kwargs):
        self.order = order
        super().__init__(*args, **kwargs)

        if order is not None:
            # Esta asignación debe ocurrir ANTES de form.is_valid().
            # Así OrderItem.clean() puede acceder a self.order.
            self.instance.order = order

            self.fields["dish"].queryset = (
                Dish.objects.filter(
                    menu__venue=order.service_session.table.venue,
                    menu__is_active=True,
                    is_available=True,
                )
                .select_related(
                    "menu",
                    "menu__venue",
                )
                .order_by(
                    "category",
                    "name",
                )
            )
        else:
            # Previene mostrar platos si el pedido no fue entregado.
            self.fields["dish"].queryset = Dish.objects.none()

        self.fields["dish"].label = "Plato"
        self.fields["quantity"].label = "Cantidad"
        self.fields["notes"].label = "Observación"

    def clean(self):
        cleaned_data = super().clean()

        if self.order is None:
            raise ValidationError(
                "No se identificó el pedido asociado."
            )

        if not self.order.can_be_edited:
            raise ValidationError(
                "El pedido ya no admite modificaciones."
            )

        dish = cleaned_data.get("dish")

        if dish and (
            dish.menu.venue_id
            != self.order.service_session.table.venue_id
        ):
            self.add_error(
                "dish",
                "El plato debe pertenecer al local del pedido.",
            )

        return cleaned_data


class OrderDiscountForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ("discount_amount",)
        widgets = {
            "discount_amount": forms.NumberInput(
                attrs={
                    "min": "0",
                    "step": "1",
                }
            ),
        }

    def clean_discount_amount(self):
        discount_amount = (
            self.cleaned_data["discount_amount"]
            or Decimal("0.00")
        )

        if discount_amount < Decimal("0.00"):
            raise ValidationError(
                "El descuento no puede ser negativo."
            )

        if discount_amount > self.instance.subtotal:
            raise ValidationError(
                "El descuento no puede ser mayor al subtotal."
            )

        return discount_amount


class PaymentForm(forms.Form):
    payment_method = forms.ChoiceField(
        label="Medio de pago",
        choices=Order.PaymentMethod.choices,
    )
    