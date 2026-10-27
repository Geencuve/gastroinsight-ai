from django import forms
from django.core.exceptions import ValidationError

from .models import Dish

MAX_IMAGE_MB = 5


class DishImageForm(forms.ModelForm):
    class Meta:
        model = Dish
        fields = ("image",)

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            raise ValidationError("Selecciona una imagen.")
        if getattr(image, "size", 0) > MAX_IMAGE_MB * 1024 * 1024:
            raise ValidationError(f"La imagen no puede superar {MAX_IMAGE_MB} MB.")
        return image
