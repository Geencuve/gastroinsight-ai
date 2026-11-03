from django.conf import settings
from django.db import models

# Create your models here.


class LegalAcceptance(models.Model):
    """Toma de conocimiento de uso educativo, términos y privacidad, por usuario y versión."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="legal_acceptances", verbose_name="Usuario")
    version = models.CharField(max_length=20, verbose_name="Versión aceptada")
    full_name = models.CharField(max_length=150, verbose_name="Nombre escrito como firma")
    accepted_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de aceptación")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Dirección IP")
    user_agent = models.CharField(max_length=255, blank=True, verbose_name="Navegador")

    class Meta:
        ordering = ["-accepted_at"]
        unique_together = ("user", "version")
        verbose_name = "Toma de conocimiento"
        verbose_name_plural = "Tomas de conocimiento"

    def __str__(self):
        return f"{self.user} — v{self.version}"
