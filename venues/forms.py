from django import forms

from .models import Venue


class VenueForm(forms.ModelForm):
    class Meta:
        model = Venue
        fields = ("name", "address", "description")
        labels = {"name": "Nombre del local", "address": "Dirección", "description": "Descripción (opcional)"}
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ej.: Restaurante Demo Providencia"}),
            "address": forms.TextInput(attrs={"placeholder": "Calle, número y comuna"}),
            "description": forms.Textarea(attrs={"rows": 2, "placeholder": "Tipo de cocina, horario o lo que ayude a identificarlo"}),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if Venue.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe un local con ese nombre.")
        return name