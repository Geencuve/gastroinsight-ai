from django import forms
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.management import call_command
from django.db import transaction
from django.shortcuts import redirect, render

from authentication.models import Profile
from cameras.models import Camera
from menus.models import Menu
from operations.models import RestaurantTable
from privacy.models import PrivacyPolicy, ProcessingAuthorization
from venues.models import Venue


class FirstRunForm(forms.Form):
    venue_name = forms.CharField(label="Nombre del local", max_length=150)
    address = forms.CharField(label="Dirección", max_length=255, required=False)
    tables = forms.IntegerField(label="Cantidad de mesas", min_value=1, max_value=60, initial=8)
    first_name = forms.CharField(label="Tu nombre", max_length=150)
    username = forms.CharField(label="Usuario administrador", max_length=150)
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Repite la contraseña", widget=forms.PasswordInput)
    load_demo = forms.BooleanField(
        label="Cargar también datos de demostración (ventas, evaluaciones y análisis de ejemplo)", required=False,
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Ese usuario ya existe.")
        return username

    def clean(self):
        data = super().clean()
        if data.get("password1") and data.get("password1") != data.get("password2"):
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif data.get("password1"):
            try:
                validate_password(data["password1"])
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return data


def first_run(request):
    """Configuración inicial cuando la aplicación se abre por primera vez."""
    if User.objects.filter(is_superuser=True).exists():
        return redirect("core:home")

    form = FirstRunForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            user = User.objects.create_superuser(
                username=data["username"], password=data["password1"], first_name=data["first_name"], email="",
            )
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = Profile.Role.PLATFORM_ADMIN
            profile.save()

            venue = Venue.objects.create(
                name=data["venue_name"], address=data["address"], is_active=True,
                description="Local configurado con el asistente de primer uso.",
            )
            profile.venues.add(venue)
            Menu.objects.create(venue=venue, name="Carta principal", description="Carta del local.", is_active=True)
            tables = [
                RestaurantTable.objects.create(venue=venue, code=f"M{number:02d}", capacity=4,
                                               zone_name="Salón principal", is_active=True)
                for number in range(1, data["tables"] + 1)
            ]
            Camera.objects.create(
                venue=venue, name="Cámara principal", source_type=Camera.SourceType.WEBCAM, source="0",
                zone_name="Salón principal", table=tables[0], is_active=True,
            )
            policy = PrivacyPolicy.objects.create(
                venue=venue, version="1.0",
                purpose=("Generar indicadores agregados de ocupación y experiencia sin identificar personas "
                         "ni guardar imágenes originales."),
                processing_enabled=True, retain_aggregated_events_days=30, retain_incidents_days=90,
                store_original_images=False, updated_by=user,
            )
            ProcessingAuthorization.objects.create(
                privacy_policy=policy, source_description="Cámara principal — salón",
                status=ProcessingAuthorization.Status.ACTIVE,
                authorization_type="Autorización interna del establecimiento", accepted_by=user,
            )
        if data["load_demo"]:
            call_command("prepare_demo")
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("/?tour=1")

    return render(request, "core/first_run.html", {"form": form})
