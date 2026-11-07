from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from assistant_chat import services
from authentication.models import Profile
from core.services.explain import ASSOCIATION, DESCRIPTIVE, annotate, method_for
from venues.models import Venue


class TransparencyTests(TestCase):
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

    def test_cada_idea_declara_su_metodo(self):
        self.assertEqual(method_for({"title": "Combo sugerido: Lomo vetado + Pisco sour"})["kind"], ASSOCIATION)
        self.assertEqual(method_for({"title": "Los jueves no son tu día"})["kind"], DESCRIPTIVE)
        result = annotate({"ventas": [{"title": "Tus ventas crecieron 34% esta semana", "impact": "$10.000"}]})
        method = result["ventas"][0]["method"]
        self.assertIn("7 días", method["calc"])
        self.assertIn("no una proyección", method["impact_note"])

    def test_sazon_explica_que_no_es_un_servicio_externo(self):
        for role in (Profile.Role.VENUE_ADMIN, Profile.Role.WAITER):
            text, intent, _ = services.build_staff_response(self._user(f"u{role}", role), "¿Qué algoritmo usas?")
            self.assertEqual(intent, "how_it_works")
            self.assertIn("no tengo costo por consulta", text)

    def test_pagina_como_funciona(self):
        self.client.force_login(self._user("sup", Profile.Role.SUPERVISOR))
        response = self.client.get("/vision/como-funciona/")
        for text in ("YOLO26", "FER+", "No se guarda", "NLIDB"):
            self.assertContains(response, text)
        self.assertContains(self.client.get("/vision/"), "Cómo funciona")
