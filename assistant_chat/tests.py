from django.test import SimpleTestCase
from django.utils import timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ChatConversation, ChatMessage
from .services import get_period_from_message


class PeriodFromMessageTests(SimpleTestCase):
    def test_mesas_hoy_no_se_interpreta_como_mes(self):
        today = timezone.localdate()

        start, end, label = get_period_from_message(
            "¿Cuántas mesas están abiertas y cuántas sesiones hubo hoy?"
        )

        self.assertEqual((start, end, label), (today, today, "hoy"))

    def test_este_mes_sigue_funcionando(self):
        today = timezone.localdate()

        start, end, label = get_period_from_message(
            "Dame el resumen de este mes"
        )

        self.assertEqual(
            (start, end, label),
            (today.replace(day=1), today, "este mes"),
        )

class StaffWidgetAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="widget_owner",
            password="test-password-123",
        )
        self.other_user = User.objects.create_user(
            username="widget_other",
            password="test-password-123",
        )

        self.conversation = ChatConversation.objects.create(
            user=self.owner,
            audience=ChatConversation.Audience.STAFF,
            title="Consulta de prueba",
        )
        ChatMessage.objects.create(
            conversation=self.conversation,
            sender=ChatMessage.Sender.USER,
            content="Dato privado de prueba",
        )

        self.url = reverse(
            "assistant_chat:staff_widget_history",
            args=[self.conversation.id],
        )

    @patch("assistant_chat.views.get_user_venues")
    def test_owner_can_read_own_history(self, mock_get_user_venues):
        mock_get_user_venues.return_value.exists.return_value = True
        self.client.force_login(self.owner)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["messages"][0]["content"],
            "Dato privado de prueba",
        )

    @patch("assistant_chat.views.get_user_venues")
    def test_other_user_cannot_post_to_history(self, mock_get_user_venues):
        mock_get_user_venues.return_value.exists.return_value = True
        self.client.force_login(self.other_user)

        message_count_before = self.conversation.messages.count()

        response = self.client.post(
            reverse("assistant_chat:staff_widget_message"),
            {
                "message": "Intento de escritura ajena",
                "conversation_id": self.conversation.id,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self.conversation.messages.count(),
            message_count_before,
        )

    @patch("assistant_chat.views.get_user_venues")
    def test_other_user_cannot_read_history(self, mock_get_user_venues):
        mock_get_user_venues.return_value.exists.return_value = True
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_cannot_read_history(self):
        response = self.client.get(self.url)

        self.assertNotEqual(response.status_code, 200)