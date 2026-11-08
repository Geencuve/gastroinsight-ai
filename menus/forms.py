from django import forms
from django.core.exceptions import ValidationError

from venues.models import Venue

from .models import Dish, Menu

MAX_IMAGE_MB = 5


def _check_size(image):
    if image and getattr(image, "size", 0) > MAX_IMAGE_MB * 1024 * 1024:
        raise ValidationError(f"La imagen no puede superar {MAX_IMAGE_MB} MB.")
    return image


class DishImageForm(forms.ModelForm):
    class Meta:
        model = Dish
        fields = ("image",)

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            raise ValidationError("Selecciona una imagen.")
        return _check_size(image)


class MenuForm(forms.ModelForm):
    class Meta:
        model = Menu
        fields = ("venue", "name", "description")
        labels = {"venue": "Local", "name": "Nombre de la carta", "description": "Descripción (opcional)"}
        widgets = {"name": forms.TextInput(attrs={"placeholder": "Ej.: Carta de almuerzo o Bebidas"}),
                   "description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, venues=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["venue"].queryset = Venue.objects.filter(pk__in=[v.pk for v in venues]).order_by("name")
        self.fields["venue"].empty_label = None

    def clean(self):
        data = super().clean()
        venue, name = data.get("venue"), (data.get("name") or "").strip()
        if venue and name and Menu.objects.filter(venue=venue, name__iexact=name).exists():
            self.add_error("name", "Ese local ya tiene una carta con ese nombre.")
        return data


class DishForm(forms.ModelForm):
    class Meta:
        model = Dish
        fields = ("name", "category", "price", "description", "is_available", "image")
        labels = {"name": "Nombre del plato", "category": "Categoría", "price": "Precio (CLP)",
                  "description": "Descripción (opcional)", "is_available": "Disponible en la carta", "image": "Foto (opcional)"}
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ej.: Pastel de choclo"}),
            "category": forms.TextInput(attrs={"list": "dish-categories", "placeholder": "Entrada, Fondo, Postre, Bebida…"}),
            "price": forms.NumberInput(attrs={"min": "0", "step": "10", "placeholder": "9490"}),
            "description": forms.Textarea(attrs={"rows": 2, "placeholder": "Ingredientes o acompañamiento"}),
            "image": forms.FileInput(attrs={"accept": "image/*"}),
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        repeated = Dish.objects.filter(menu_id=self.instance.menu_id, name__iexact=name).exclude(pk=self.instance.pk)
        if repeated.exists():
            raise ValidationError("Ya existe un plato con ese nombre en esta carta.")
        return name

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price is None or price < 0:
            raise ValidationError("El precio no puede ser negativo.")
        return price

    def clean_image(self):
        return _check_size(self.cleaned_data.get("image"))