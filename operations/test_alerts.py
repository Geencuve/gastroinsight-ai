from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from authentication.models import Profile
from cameras.models import Camera
from operations.models import Notification, RestaurantTable, ServiceSession, WaitlistEntry
from operations.services.notifications import generate
from venues.models import Venue


class AlertsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.venue = Venue.objects.create(name="Local de prueba")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="M1", capacity=4)
        self.session = ServiceSession.objects.create(table=self.table, guests_count=2)
        self.camera = Camera.objects.create(venue=self.venue, name="Cam M1", source="demo",
                                            source_type=Camera.SourceType.DEMO, table=self.table)
        self.analysis = AnalysisSession.objects.create(camera=self.camera, status="running")

    def _user(self, name, role):
        user = User.objects.create_user(name, password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(self.venue)
        return user

    def _event(self, **values):
        return DetectionEvent.objects.create(session=self.analysis, faces_count=2, table=self.table,
                                             service_session=self.session, occupancy=Decimal("2"), **values)

    def test_busca_atencion_crea_una_sola_alerta(self):
        self._event(attention_seeking=Decimal("0.5"), experience_index=Decimal("60"))
        generate(Venue.objects.all())
        cache.clear()
        generate(Venue.objects.all())
        self.assertEqual(Notification.objects.filter(kind="attention").count(), 1)

    def test_disconformidad_y_aprobacion(self):
        self._event(experience_index=Decimal("38"))
        generate(Venue.objects.all())
        self.assertTrue(Notification.objects.filter(kind="discomfort", level="danger").exists())

    def test_ingreso_por_lista_de_espera_y_camara_de_entrada(self):
        WaitlistEntry.objects.create(venue=self.venue, guests=4, party_name="Familia Soto")
        entrance = Camera.objects.create(venue=self.venue, name="Entrada", source="demo",
                                         source_type=Camera.SourceType.DEMO, is_entrance=True)
        analysis = AnalysisSession.objects.create(camera=entrance, status="running")
        first = DetectionEvent.objects.create(session=analysis, faces_count=0, persons_detected=Decimal("1"))
        DetectionEvent.objects.filter(pk=first.pk).update(detected_at=timezone.now() - timedelta(seconds=30))
        DetectionEvent.objects.create(session=analysis, faces_count=0, persons_detected=Decimal("4"))
        generate(Venue.objects.all())
        titles = list(Notification.objects.filter(kind="arrival").values_list("title", flat=True))
        self.assertIn("Llegó un grupo de 4", titles)
        self.assertIn("Ingresan 3 persona(s)", titles)

    def test_garzon_recibe_alertas_y_cocina_no(self):
        self._event(attention_seeking=Decimal("0.5"))
        self.client.force_login(self._user("garzon", Profile.Role.WAITER))
        data = self.client.get("/notificaciones/").json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["kind"], "attention")
        self.client.post(data["items"][0]["ack_url"])
        self.assertEqual(self.client.get("/notificaciones/").json()["count"], 0)
        self.client.force_login(self._user("cocinero", Profile.Role.KITCHEN))
        self.assertEqual(self.client.get("/notificaciones/").json()["count"], 0)

    def test_vista_del_garzon(self):
        self.client.force_login(self._user("garzona", Profile.Role.WAITER))
        self.assertRedirects(self.client.get("/"), "/garzon/", fetch_redirect_response=False)
        response = self.client.get("/garzon/")
        self.assertContains(response, "Mis alertas")
        self.assertContains(response, "js/alerts.js")
