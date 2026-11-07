from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from authentication.models import Profile
from cameras.models import Camera
from operations.models import AlertSettings, Notification, RestaurantTable, ServiceSession
from operations.services.notifications import generate
from operations.services.sustained import impatience
from venues.models import Venue


class SustainedAlertTests(TestCase):
    def setUp(self):
        cache.clear()
        self.venue = Venue.objects.create(name="Local")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="M4", capacity=4)
        self.session = ServiceSession.objects.create(table=self.table, guests_count=2)
        camera = Camera.objects.create(venue=self.venue, name="Cam M4", source="demo",
                                       source_type=Camera.SourceType.DEMO, table=self.table)
        self.analysis = AnalysisSession.objects.create(camera=camera, status="running")

    def _readings(self, minutes, attention, ieo, every=1):
        now = timezone.now()
        for minute in range(minutes, -1, -every):
            event = DetectionEvent.objects.create(session=self.analysis, faces_count=2, table=self.table,
                                                  service_session=self.session, occupancy=Decimal("2"),
                                                  attention_seeking=Decimal(attention), experience_index=Decimal(ieo))
            DetectionEvent.objects.filter(pk=event.pk).update(detected_at=now - timedelta(minutes=minute, seconds=-5))

    def test_formula_de_impaciencia(self):
        self.assertEqual(impatience(Decimal("0.9"), Decimal("30")), 82.0)

    def test_impaciencia_sostenida_genera_alerta(self):
        self._readings(10, "0.9", "30")
        generate(Venue.objects.all())
        alert = Notification.objects.get(kind="impatience")
        self.assertIn("durante 8 min", alert.title)
        self.assertIn("Mesa M4", alert.title)

    def test_un_pico_breve_no_genera_alerta(self):
        self._readings(2, "0.9", "30")
        generate(Venue.objects.all())
        self.assertFalse(Notification.objects.filter(kind="impatience").exists())

    def test_umbral_configurable_como_el_ejemplo_de_la_docente(self):
        AlertSettings.objects.create(venue=self.venue, impatience_pct=80, impatience_minutes=12)
        self._readings(10, "0.9", "30")
        generate(Venue.objects.all())
        self.assertFalse(Notification.objects.filter(kind="impatience").exists())
        cache.clear()
        self._readings(13, "0.95", "20")
        generate(Venue.objects.all())
        self.assertIn("durante 12 min", Notification.objects.get(kind="impatience").title)

    def test_centro_de_gestion_guarda_los_umbrales(self):
        user = User.objects.create_user("duena", password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.VENUE_ADMIN
        profile.save()
        profile.venues.add(self.venue)
        self.client.force_login(user)
        self.assertContains(self.client.get("/gestion/"), "Umbrales de alerta por local")
        prefix = f"v{self.venue.id}"
        self.client.post(f"/gestion/alertas/{self.venue.id}/", {
            f"{prefix}-impatience_pct": "80", f"{prefix}-impatience_minutes": "12", f"{prefix}-discomfort_ieo": "45",
            f"{prefix}-discomfort_minutes": "5", f"{prefix}-waiting_minutes": "15", f"{prefix}-approval_ieo": "80"})
        settings = AlertSettings.objects.get(venue=self.venue)
        self.assertEqual((settings.impatience_pct, settings.impatience_minutes, settings.waiting_minutes), (80, 12, 15))
