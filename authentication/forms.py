from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
)
from django.contrib.auth.models import User


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Usuario",
        widget=forms.TextInput(
            attrs={
                "class": "form-input",
                "placeholder": "Ingresa tu usuario",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-input",
                "placeholder": "Ingresa tu contraseña",
            }
        ),
    )


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(
        label="Nombre",
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-input"}
        ),
    )
    last_name = forms.CharField(
        label="Apellido",
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={"class": "form-input"}
        ),
    )
    email = forms.EmailField(
        label="Correo electrónico",
        required=True,
        widget=forms.EmailInput(
            attrs={"class": "form-input"}
        ),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "form-input",
            )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Ya existe un usuario registrado con este correo."
            )

        return email


class AccountForm(forms.ModelForm):
    """Datos editables de la cuenta desde Mi perfil."""

    phone = forms.CharField(label="Teléfono", max_length=30, required=False,
                            widget=forms.TextInput(attrs={"placeholder": "+56 9 1234 5678"}))

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        labels = {"first_name": "Nombre", "last_name": "Apellido", "email": "Correo electrónico"}

    def __init__(self, *args, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.profile = profile
        if profile is not None and not self.is_bound:
            self.fields["phone"].initial = profile.phone

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ese correo ya está registrado en otra cuenta.")
        return email

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit and self.profile is not None:
            self.profile.phone = self.cleaned_data.get("phone", "").strip()
            self.profile.save(update_fields=["phone", "updated_at"])
        return user
