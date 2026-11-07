import time
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from authentication.models import Profile
from cameras.models import Camera
from operations.models import RestaurantTable, SatisfactionEvaluation, ServiceSession, WaitlistEntry
from operations.services.floor import build_floor, session_state, thermometer
from operations.views_floor import session_token
from sales.models import Order
from venues.models import Venue


class FloorAndCashierTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local de prueba")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="M1", capacity=4)
        self.free = RestaurantTable.objects.create(venue=self.venue, code="M2", capacity=4)
        self.user = User.objects.create_user("jefe", password="Test12345!", is_superuser=True, is_staff=True)
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.session = ServiceSession.objects.create(table=self.table, guests_count=2, created_by=self.user)

    def _order(self, status):
        order = Order.objects.create(service_session=self.session, created_by=self.user)
        Order.objects.filter(pk=order.pk).update(status=status)
        return Order.objects.get(pk=order.pk)

    def test_estados_de_la_mesa(self):
        self.assertEqual(session_state(self.session, []), "esperando_pedido")
        confirmed = self._order(Order.Status.CONFIRMED)
        self.assertEqual(session_state(self.session, [confirmed]), "consumiendo")
        self.session.bill_requested_at = timezone.now()
        self.assertEqual(session_state(self.session, [confirmed]), "cuenta")
        paid = self._order(Order.Status.PAID)
        self.assertEqual(session_state(self.session, [paid]), "por_cerrar")

    def test_mapa_de_sala_con_mesas_libres_y_ocupadas(self):
        floor = build_floor(Venue.objects.all())
        states = {card["table"].code: card["state"] for _, cards in floor["zones"] for card in cards}
        self.assertEqual(states, {"M1": "esperando_pedido", "M2": "libre"})
        self.client.force_login(self.user)
        self.assertContains(self.client.get("/sala/"), "Mapa de sala")

    def test_lista_de_espera_asigna_mesa_y_mide_la_espera(self):
        self.client.force_login(self.user)
        self.client.post("/sala/espera/", {"guests": 3, "party_name": "Familia Soto"})
        entry = WaitlistEntry.objects.get()
        WaitlistEntry.objects.filter(pk=entry.pk).update(arrived_at=timezone.now() - timedelta(minutes=12))
        self.client.post(f"/sala/espera/{entry.pk}/asignar/", {"table": self.free.pk})
        session = ServiceSession.objects.get(table=self.free, status=ServiceSession.Status.OPEN)
        self.assertEqual(session.guests_count, 3)
        self.assertGreaterEqual((session.started_at - session.arrived_at).total_seconds(), 11 * 60)

    def test_qr_por_atencion_guarda_infraestructura_una_sola_vez(self):
        url = f"/opinion/atencion/{session_token(self.session)}/"
        self.assertContains(self.client.get(url), "precio-calidad")
        data = {"rating": "4", "value_rating": "5", "return_intent": "yes", "cleanliness_rating": "5",
                "restroom_rating": "3", "ambience_rating": "4", "comment": "Muy rico"}
        self.client.post(url, data)
        evaluation = SatisfactionEvaluation.objects.get()
        self.assertEqual((evaluation.value_rating, evaluation.return_intent, evaluation.restroom_rating), (5, "yes", 3))
        self.assertEqual(evaluation.source, SatisfactionEvaluation.Source.CUSTOMER_QR)
        self.client.post(url, {**data, "rating": "1"})
        self.assertEqual(SatisfactionEvaluation.objects.count(), 1)

    def test_qr_caduca_a_las_tres_horas(self):
        token = session_token(self.session)
        with mock.patch("django.core.signing.time.time", return_value=time.time() + 3 * 3600 + 60):
            response = self.client.get(f"/opinion/atencion/{token}/")
        self.assertEqual(response.status_code, 410)

    def test_termometro_en_rojo_y_visible_en_caja(self):
        camera = Camera.objects.create(venue=self.venue, name="Cam", source="demo",
                                       source_type=Camera.SourceType.DEMO, table=self.table)
        analysis = AnalysisSession.objects.create(camera=camera, status="completed")
        for _ in range(3):
            DetectionEvent.objects.create(session=analysis, faces_count=2, table=self.table, service_session=self.session,
                                          experience_index=Decimal("40"), attention_seeking=Decimal("0.4"))
        result = thermometer(self.session)
        self.assertEqual(result["level"], "rojo")
        self.assertIn("cortesía", result["suggestion"])
        self._order(Order.Status.CONFIRMED)
        self.client.force_login(self.user)
        self.assertContains(self.client.get("/caja/"), "Experiencia en riesgo")

    def test_mesero_y_caja_llegan_a_su_seccion(self):
        for role, home in ((Profile.Role.WAITER, "/sala/"), (Profile.Role.CASHIER, "/caja/")):
            user = User.objects.create_user(f"u_{role}", password="Test12345!")
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = role
            profile.save()
            profile.venues.add(self.venue)
            self.client.force_login(user)
            self.assertRedirects(self.client.get("/"), home, fetch_redirect_response=False)
            self.assertEqual(self.client.get(home).status_code, 200)
