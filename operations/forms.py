from django import forms
from django.core.exceptions import ValidationError
from menus.models import Dish
from .models import RestaurantTable, ServiceSession,SatisfactionEvaluation


class RestaurantTableForm(forms.ModelForm):
    class Meta:
        model = RestaurantTable
        fields = (
            "code",
            "capacity",
            "zone_name",
            "is_active",
            "notes",
        )
        widgets = {
            "code": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Ejemplo: M01",
                }
            ),
            "capacity": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "min": 1,
                }
            ),
            "zone_name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Ejemplo: Salón principal",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 3,
                }
            ),
        }

    def __init__(self, *args, venue=None, **kwargs):
        self.venue = venue
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()

        if not code:
            raise ValidationError(
                "Debes indicar un código para la mesa."
            )

        if self.venue:
            duplicate = RestaurantTable.objects.filter(
                venue=self.venue,
                code__iexact=code,
            )

            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)

            if duplicate.exists():
                raise ValidationError(
                    "Ya existe una mesa con este código en el local."
                )

        return code


class ServiceSessionForm(forms.ModelForm):
    class Meta:
        model = ServiceSession
        fields = (
            "table",
            "guests_count",
            "notes",
        )
        widgets = {
            "table": forms.Select(
                attrs={"class": "form-input"}
            ),
            "guests_count": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "min": 1,
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 3,
                    "placeholder": "Observaciones opcionales",
                }
            ),
        }

    def __init__(self, *args, venues=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["table"].queryset = (
            RestaurantTable.objects.filter(
                is_active=True,
                venue__is_active=True,
            )
            .select_related("venue")
            .order_by("venue__name", "code")
        )

        if venues is not None:
            self.fields["table"].queryset = (
                self.fields["table"]
                .queryset.filter(venue__in=venues)
            )

    def clean_table(self):
        table = self.cleaned_data["table"]

        if ServiceSession.objects.filter(
            table=table,
            status=ServiceSession.Status.OPEN,
        ).exists():
            raise ValidationError(
                "Esta mesa ya tiene una sesión de atención abierta."
            )

        return table

class SatisfactionEvaluationForm(forms.ModelForm):
    class Meta:
        model = SatisfactionEvaluation
        fields = (
            "service_session",
            "dish",
            "rating",
            "comment",
        )
        widgets = {
            "service_session": forms.Select(
                attrs={"class": "form-input"}
            ),
            "dish": forms.Select(
                attrs={"class": "form-input"}
            ),
            "rating": forms.Select(
                attrs={"class": "form-input"}
            ),
            "comment": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 4,
                    "maxlength": 500,
                    "placeholder": (
                        "Comentario opcional. "
                        "No ingreses datos personales."
                    ),
                }
            ),
        }

    def __init__(self, *args, venues=None, **kwargs):
        super().__init__(*args, **kwargs)

        sessions = (
            ServiceSession.objects.filter(
                table__is_active=True,
                table__venue__is_active=True,
            )
            .select_related(
                "table",
                "table__venue",
            )
            .order_by("-started_at")
        )

        dishes = (
            Dish.objects.filter(
                is_available=True,
                menu__is_active=True,
                menu__venue__is_active=True,
            )
            .select_related(
                "menu",
                "menu__venue",
            )
            .order_by(
                "menu__venue__name",
                "menu__name",
                "name",
            )
        )

        if venues is not None:
            sessions = sessions.filter(
                table__venue__in=venues
            )
            dishes = dishes.filter(
                menu__venue__in=venues
            )

        self.fields["service_session"].queryset = sessions
        self.fields["dish"].queryset = dishes

    def clean(self):
        cleaned_data = super().clean()

        service_session = cleaned_data.get("service_session")
        dish = cleaned_data.get("dish")

        if service_session and dish:
            session_venue_id = service_session.table.venue_id
            dish_venue_id = dish.menu.venue_id

            if session_venue_id != dish_venue_id:
                self.add_error(
                    "dish",
                    (
                        "El plato debe pertenecer al mismo local "
                        "que la sesión de atención seleccionada."
                    ),
                )

        return cleaned_data