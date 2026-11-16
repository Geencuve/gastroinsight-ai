"""CR-01: la telemetria solo se acepta con politica habilitada y autorizacion vigente."""
import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from ai_vision.models import DetectionEvent
from cameras.models import Camera
from operations.api import new_key
from operations.models import ApiKey, RestaurantTable
from privacy.models import PrivacyPolicy, ProcessingAuthorization
from venues.models import Venue


class TelemetriaExigeAutorizacionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.venue = Venue.objects.create(name="Local CR-01")
        self.user = User.objects.create_user("admin_cr01", password="Clave#Segura2026")
        table = RestaurantTable.objects.create(venue=self.venue, code="T01", capacity=4)
        self.camera = Camera.objects.create(venue=self.venue, name="Camara CR-01", source="0", table=table)
        raw, _prefix, key_hash = new_key()
        ApiKey.objects.create(venue=self.venue, name="prueba", key_hash=key_hash, created_by=self.user)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {raw}"}

    def _enviar(self):
        body = {"camara": self.camera.pk, "rostros": 2, "ibe": 0.4, "atencion": 0.1}
        return self.client.post("/api/v1/telemetria/", json.dumps(body), content_type="application/json", **self.auth)

    def _politica(self, habilitada=True):
        return PrivacyPolicy.objects.create(venue=self.venue, purpose="Indicadores agregados por mesa", processing_enabled=habilitada)

    def _autorizar(self, politica, **extra):
        ProcessingAuthorization.objects.create(privacy_policy=politica, source_description="Salon principal", **extra)

    def test_sin_politica_rechaza_y_no_guarda(self):
        self.assertEqual(self._enviar().status_code, 403)
        self.assertEqual(DetectionEvent.objects.count(), 0)

    def test_politica_deshabilitada_rechaza(self):
        self._autorizar(self._politica(habilitada=False))
        self.assertEqual(self._enviar().status_code, 403)
        self.assertEqual(DetectionEvent.objects.count(), 0)

    def test_autorizacion_vencida_rechaza(self):
        self._autorizar(self._politica(), expires_at=timezone.now() - timedelta(days=1))
        self.assertEqual(self._enviar().status_code, 403)
        self.assertEqual(DetectionEvent.objects.count(), 0)

    def test_autorizacion_revocada_rechaza(self):
        self._autorizar(self._politica(), status=ProcessingAuthorization.Status.REVOKED)
        self.assertEqual(self._enviar().status_code, 403)

    def test_autorizacion_vigente_acepta(self):
        self._autorizar(self._politica())
        response = self._enviar()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(DetectionEvent.objects.count(), 1)