from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from authentication.models import Profile
from menus.models import Dish, Menu
from operations.feedback import table_token
from operations.models import RestaurantTable, SatisfactionEvaluation, ServiceSession
from venues.models import Venue


class CustomerFeedbackTests(TestCase):
    def setUp(self):
        venue = Venue.objects.create(name="Local de prueba")
        menu = Menu.objects.create(venue=venue, name="Carta")
        self.dish = Dish.objects.create(menu=menu, name="Tiramisú", category="Postre", price=5990)
        self.table = RestaurantTable.objects.create(venue=venue, code="X1", capacity=4)
        self.session = ServiceSession.objects.create(table=self.table, guests_count=2)
        self.url = f"/opinion/{table_token(self.table)}/"

    def test_cliente_califica_por_qr(self):
        response = self.client.post(self.url, {"rating": "5", "dish": self.dish.id, "comment": "Excelente"})
        self.assertEqual(response.status_code, 302)
        evaluation = SatisfactionEvaluation.objects.get()
        self.assertEqual(evaluation.source, SatisfactionEvaluation.Source.CUSTOMER_QR)
        self.assertEqual(evaluation.service_session, self.session)
        self.assertIsNone(evaluation.registered_by)

    def test_no_permite_doble_envio_desde_el_mismo_navegador(self):
        self.client.post(self.url, {"rating": "4"})
        self.client.post(self.url, {"rating": "1"})
        self.assertEqual(SatisfactionEvaluation.objects.count(), 1)

    def test_codigo_alterado_es_rechazado(self):
        response = self.client.get(f"/opinion/{self.table.id}:firmafalsa/")
        self.assertEqual(response.status_code, 404)

    def test_sin_atencion_activa_muestra_aviso(self):
        ServiceSession.objects.filter(pk=self.session.pk).update(
            status="closed", ended_at=timezone.now() - timedelta(hours=5),
        )
        response = self.client.get(self.url)
        self.assertContains(response, "no hay una atención activa")

    def test_pagina_de_codigos_qr(self):
        user = User.objects.create_user("admin2", password="Test12345!", is_staff=True, is_superuser=True)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.client.force_login(user)
        response = self.client.get("/opinion/qr/")
        self.assertContains(response, "Mesa X1")
        self.assertContains(response, "<svg")
