from django.conf import settings
from django.db import models

from venues.models import Venue


class ChatConversation(models.Model):
    class Audience(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Cliente"
        STAFF = "STAFF", "Trabajador del local"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="chat_conversations",
    )
    venue = models.ForeignKey(
        Venue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_conversations",
    )
    audience = models.CharField(
        max_length=20,
        choices=Audience.choices,
    )
    title = models.CharField(
        max_length=160,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return self.title or f"Conversación #{self.pk}"


class ChatMessage(models.Model):
    class Sender(models.TextChoices):
        USER = "USER", "Usuario"
        ASSISTANT = "ASSISTANT", "Asistente"
        SYSTEM = "SYSTEM", "Sistema"

    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.CharField(
        max_length=20,
        choices=Sender.choices,
    )
    content = models.TextField()
    intent = models.CharField(
        max_length=80,
        blank=True,
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.sender}: {self.content[:60]}"