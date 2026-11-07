from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

from cameras.models import Camera
from operations.models import RestaurantTable

from .models import Profile
from .roles import (BAR, CASHIER, KITCHEN, OPERATOR, PLATFORM_ADMIN, SUPERVISOR, VENUE_ADMIN, VIEWER, WAITER,
                    role_key)

MANAGEMENT_ROLES = {PLATFORM_ADMIN, VENUE_ADMIN, SUPERVISOR}
LABELS = dict(Profile.Role.choices)


def is_manager(user):
    from .permissions import get_or_create_profile

    return user.is_superuser or role_key(get_or_create_profile(user)) in MANAGEMENT_ROLES


def assignable_roles(actor):
    key = role_key(actor)
    roles = [WAITER, KITCHEN, BAR, CASHIER, OPERATOR, VIEWER]
    if key in (VENUE_ADMIN, PLATFORM_ADMIN) or actor.user.is_superuser:
        roles += [SUPERVISOR, VENUE_ADMIN]
    if key == PLATFORM_ADMIN or actor.user.is_superuser:
        roles += [PLATFORM_ADMIN]
    return roles


class _StaffBase(forms.Form):
    role = forms.ChoiceField(label="Rol")
    venues = forms.ModelMultipleChoiceField(label="Locales", queryset=None, widget=forms.CheckboxSelectMultiple)
    zones = forms.CharField(label="Zonas (opcional)", required=False, max_length=200,
                            help_text="Por ejemplo: Salón, Terraza. Vacío = todas las zonas.")

    def __init__(self, *args, actor=None, venues=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.fields["role"].choices = [(r, LABELS.get(r, r)) for r in assignable_roles(actor)]
        self.fields["venues"].queryset = venues


class StaffCreateForm(_StaffBase):
    first_name = forms.CharField(label="Nombre", max_length=150)
    last_name = forms.CharField(label="Apellido", max_length=150, required=False)
    username = forms.CharField(label="Usuario", max_length=150)
    password = forms.CharField(label="Contraseña inicial", widget=forms.PasswordInput(render_value=False))
    field_order = ["first_name", "last_name", "username", "password", "role", "venues", "zones"]

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Ese usuario ya existe.")
        return username

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(data["username"], password=data["password"], first_name=data["first_name"],
                                        last_name=data["last_name"])
        _apply(user, data)
        return user


class StaffEditForm(_StaffBase):
    is_active = forms.BooleanField(label="Cuenta activa", required=False)
    new_password = forms.CharField(label="Nueva contraseña (opcional)", required=False,
                                   widget=forms.PasswordInput(render_value=False))

    def clean_new_password(self):
        password = self.cleaned_data.get("new_password")
        if password:
            validate_password(password)
        return password

    def save(self, user):
        data = self.cleaned_data
        user.is_active = data["is_active"]
        if data.get("new_password"):
            user.set_password(data["new_password"])
        user.save()
        _apply(user, data)
        return user


def _apply(user, data):
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.role = data["role"]
    profile.zones = ", ".join(z.strip() for z in data["zones"].split(",") if z.strip())
    profile.save()
    profile.venues.set(data["venues"])
    if data["role"] in (PLATFORM_ADMIN, VENUE_ADMIN) and not user.is_staff:
        user.is_staff = True
        user.save(update_fields=["is_staff"])


class TableForm(forms.ModelForm):
    class Meta:
        model = RestaurantTable
        fields = ["venue", "code", "capacity", "zone_name"]
        labels = {"venue": "Local", "code": "Código", "capacity": "Capacidad", "zone_name": "Zona"}

    def __init__(self, *args, venues=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["venue"].queryset = venues


class CameraForm(forms.ModelForm):
    class Meta:
        model = Camera
        fields = ["name", "venue", "source_type", "source", "table", "zone_name", "is_entrance", "is_checkout", "is_active"]
        labels = {"name": "Nombre", "venue": "Local", "source_type": "Tipo de fuente", "source": "Fuente (0 = webcam)",
                  "table": "Mesa", "zone_name": "Zona", "is_entrance": "Cámara de entrada", "is_checkout": "Cámara de caja", "is_active": "Activa"}

    def __init__(self, *args, venues=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["venue"].queryset = venues
        self.fields["table"].queryset = RestaurantTable.objects.filter(venue__in=venues).order_by("code")
        self.fields["table"].required = False
