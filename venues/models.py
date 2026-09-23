from django.db import models


class Venue(models.Model):
    name = models.CharField(
        max_length=150,
        verbose_name="Nombre del local",
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Dirección",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Descripción",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última actualización",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Local"
        verbose_name_plural = "Locales"

    def __str__(self):
        return self.name