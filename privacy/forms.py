from django import forms

from .models import PrivacyPolicy, ProcessingAuthorization


class PrivacyPolicyForm(forms.ModelForm):
    class Meta:
        model = PrivacyPolicy
        fields = (
            "version",
            "purpose",
            "processing_enabled",
            "retain_aggregated_events_days",
            "retain_incidents_days",
            "store_original_images",
        )
        widgets = {
            "version": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Ejemplo: 1.0",
                }
            ),
            "purpose": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 5,
                }
            ),
            "retain_aggregated_events_days": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "min": 1,
                    "max": 365,
                }
            ),
            "retain_incidents_days": forms.NumberInput(
                attrs={
                    "class": "form-input",
                    "min": 1,
                    "max": 730,
                }
            ),
        }

    def clean_store_original_images(self):
        store_images = self.cleaned_data["store_original_images"]

        if store_images:
            raise forms.ValidationError(
                (
                    "El MVP no permite almacenar imágenes originales. "
                    "El procesamiento debe generar solo eventos agregados."
                )
            )

        return store_images


class ProcessingAuthorizationForm(forms.ModelForm):
    class Meta:
        model = ProcessingAuthorization
        fields = (
            "source_description",
            "authorization_type",
            "status",
            "expires_at",
            "notes",
        )
        widgets = {
            "source_description": forms.TextInput(
                attrs={"class": "form-input"}
            ),
            "authorization_type": forms.TextInput(
                attrs={"class": "form-input"}
            ),
            "status": forms.Select(
                attrs={"class": "form-input"}
            ),
            "expires_at": forms.DateTimeInput(
                attrs={
                    "class": "form-input",
                    "type": "datetime-local",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 4,
                }
            ),
        }