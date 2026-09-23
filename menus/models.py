from django.db import models

from venues.models import Venue


class Menu(models.Model):
    venue = models.ForeignKey(
        Venue,
        on_delete=models.CASCADE,
        related_name="menus",
        verbose_name="Local",
    )
    name = models.CharField(
        max_length=150,
        verbose_name="Nombre del menú",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Descripción",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["venue__name", "name"]
        verbose_name = "Menú"
        verbose_name_plural = "Menús"
        constraints = [
            models.UniqueConstraint(
                fields=["venue", "name"],
                name="unique_menu_per_venue",
            )
        ]

    def __str__(self):
        return f"{self.name} — {self.venue.name}"


class Dish(models.Model):
    menu = models.ForeignKey(
        Menu,
        on_delete=models.CASCADE,
        related_name="dishes",
        verbose_name="Menú",
    )
    name = models.CharField(
        max_length=150,
        verbose_name="Nombre del plato",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Descripción",
    )
    category = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Categoría",
        help_text="Ejemplo: Entrada, Fondo, Postre, Bebida.",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Precio",
    )
    is_available = models.BooleanField(
        default=True,
        verbose_name="Disponible",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["menu__name", "category", "name"]
        verbose_name = "Plato"
        verbose_name_plural = "Platos"
        constraints = [
            models.UniqueConstraint(
                fields=["menu", "name"],
                name="unique_dish_per_menu",
            )
        ]

    def __str__(self):
        return f"{self.name} — {self.menu.name}"