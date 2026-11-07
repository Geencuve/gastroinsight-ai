from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from assistant_chat import services
from assistant_chat.robust import expand, fuzzy_candidates
from authentication.models import Profile
from venues.models import Venue


class RobustSazonTests(TestCase):
    def setUp(self):
        cache.clear()
        self.venue = Venue.objects.create(name="Local")

    def _user(self, name, role):
        user = User.objects.create_user(name, password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(self.venue)
        return user

    def test_sinonimos_y_chilenismos(self):
        self.assertIn("ticket promedio", expand("cual es la boleta promedio"))
        self.assertEqual(services.classify_intent("¿Cuál es la boleta promedio?", "STAFF"), "average_ticket")

    def test_tolera_errores_de_tipeo(self):
        self.assertEqual(services.classify_intent("¿Qué es lo mas vendidp?", "STAFF"), "top_dishes")

    def test_la_consulta_exacta_no_cambia(self):
        self.assertEqual(services.classify_intent("¿Cuál es el ticket promedio?", "STAFF"), "average_ticket")
        self.assertEqual(services.classify_intent("¿Cómo están las mesas ahora?", "STAFF"), "live_status")

    def test_consulta_vacia(self):
        _, intent, _ = services.build_staff_response(self._user("a", Profile.Role.VENUE_ADMIN), "???")
        self.assertEqual(intent, "empty")

    def test_preguntas_de_seguimiento_filtradas_por_rol(self):
        _, intent, meta = services.build_staff_response(self._user("jefa", Profile.Role.VENUE_ADMIN), "¿Qué es lo más vendido?")
        self.assertEqual(intent, "top_dishes")
        self.assertTrue(meta["followups"])
        self.assertIn("elapsed_ms", meta)
        _, intent, meta = services.build_staff_response(self._user("cocina", Profile.Role.KITCHEN), "¿Cómo va la cocina?")
        prompts = [f["prompt"] for f in meta["followups"]]
        self.assertNotIn("¿Cuánto vendimos hoy?", prompts)

    def test_quisiste_decir_ofrece_opciones_cercanas(self):
        candidates = dict(fuzzy_candidates("tikcet promedo", services.STAFF_RULES))
        self.assertIn("average_ticket", candidates)

    def test_widget_devuelve_seguimiento_y_tiempo(self):
        self.client.force_login(self._user("dueno", Profile.Role.VENUE_ADMIN))
        data = self.client.post("/assistant/staff/widget/message/", {"message": "¿Qué es lo más vendido?"}).json()
        self.assertIn("followups", data)
        self.assertIn("elapsed_ms", data)

    def test_error_interno_responde_con_amabilidad(self):
        from unittest import mock

        user = self._user("x", Profile.Role.VENUE_ADMIN)
        with mock.patch("assistant_chat.services.get_user_venues", side_effect=RuntimeError("falla")):
            text, intent, _ = services.build_staff_response(user, "¿Cuál es el ticket promedio?")
        self.assertEqual(intent, "error")
        self.assertIn("No pude calcular", text)
