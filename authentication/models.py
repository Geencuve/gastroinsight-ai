from django.conf import settings
from django.db import models

from venues.models import Venue


class Profile(models.Model):
    class Role(models.TextChoices):
        PLATFORM_ADMIN = "platform_admin", "Administrador de plataforma"
        VENUE_ADMIN = "venue_admin", "Administrador de local"
        OPERATOR = "operator", "Operador"
        VIEWER = "viewer", "Visualizador"
        SUPERVISOR = "supervisor", "Supervisor"
        WAITER = "waiter", "Mesero"
        KITCHEN = "kitchen", "Cocina"
        BAR = "bar", "Barra"
        CASHIER = "cashier", "Caja"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Usuario",
    )
    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.VIEWER,
        verbose_name="Rol",
    )
    venues = models.ManyToManyField(
        Venue,
        blank=True,
        related_name="assigned_profiles",
        verbose_name="Locales asignados",
    )
    phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Teléfono",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"

    def __str__(self):
        return (
            f"{self.user.get_username()} — "
            f"{self.get_role_display()}"
        )

    @property
    def is_platform_admin(self):
        return self.role == self.Role.PLATFORM_ADMIN or self.user.is_superuser

    @property
    def is_venue_admin(self):
        return self.role == self.Role.VENUE_ADMIN

    @property
    def can_manage_venue_data(self):
        return self.is_platform_admin or self.is_venue_admin

    def can_access_venue(self, venue):
        if self.is_platform_admin:
            return True

        return self.venues.filter(id=venue.id).exists()