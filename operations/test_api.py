import json
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from ai_vision.models import DetectionEvent
from cameras.models import Camera
from menus.models import Dish, Menu
from operations.api import hash_key, new_key
from operations.models import ApiKey, RestaurantTable
from sales.models import Order
from venues.models import Venue


class IntegrationApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("jefa", password="Test12345!", is_superuser=True, is_staff=True)
        self.venue = Venue.objects.create(name="Local")
        self.other = Venue.objects.create(name="Otro local")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="M01", capacity=4)
        self.camera = Camera.objects.create(venue=self.venue, name="Cam", source="demo",
                                            source_type=Camera.SourceType.DEMO, table=self.table)
        self.foreign_camera = Camera.objects.create(venue=self.other, name="Ajena", source="demo",
                                                    source_type=Camera.SourceType.DEMO)
        Dish.objects.create(menu=Menu.objects.create(venue=self.venue, name="Carta"), name="Lomo vetado",
                            category="Fondo", price=Decimal("15990"))
        raw, prefix, digest = new_key()
        self.key = ApiKey.objects.create(venue=self.venue, name="Caja", prefix=prefix, key_hash=digest, created_by=self.admin)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {raw}"}

    def _post(self, url, data, **extra):
        return self.client.post(url, json.dumps(data), content_type="application/json", **{**self.auth, **extra})

    def test_estado_requiere_clave_valida(self):
        self.assertEqual(self.client.get("/api/v1/estado/").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/estado/", **self.auth).json()["local"], "Local")

    def test_telemetria_crea_lectura_y_calcula_el_ieo(self):
        response = self._post("/api/v1/telemetria/", {"camara": self.camera.id, "rostros": 2, "ibe": -0.2, "atencion": 0.6})
        self.assertEqual(response.status_code, 201)
        event = DetectionEvent.objects.get(pk=response.json()["evento"])
        self.assertEqual(event.table, self.table)
        self.assertIsNotNone(event.experience_index)

    def test_telemetria_valida_rangos_y_local(self):
        self.assertEqual(self._post("/api/v1/telemetria/", {"camara": self.camera.id, "ibe": 3}).status_code, 400)
        self.assertEqual(self._post("/api/v1/telemetria/", {"camara": self.foreign_camera.id}).status_code, 404)

    def test_ventas_crea_pedido_pagado_sin_duplicar(self):
        sale = {"pedido_externo": "POS-1", "mesa": "M01", "items": [{"plato": "lomo vetado", "cantidad": 2}]}
        response = self._post("/api/v1/ventas/", sale)
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.json()["pedido"])
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(int(order.total), 31980)
        self.assertTrue(self._post("/api/v1/ventas/", sale).json()["duplicado"])
        self.assertEqual(Order.objects.count(), 1)

    def test_ventas_rechaza_platos_desconocidos(self):
        response = self._post("/api/v1/ventas/", {"pedido_externo": "POS-2", "mesa": "M01", "items": [{"plato": "Sushi", "cantidad": 1}]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detalles"]["desconocidos"], ["Sushi"])

    def test_clave_revocada_y_solo_se_guarda_la_huella(self):
        self.assertNotIn("gi_", self.key.key_hash)
        self.assertEqual(self.key.key_hash, hash_key(self.auth["HTTP_AUTHORIZATION"][7:]))
        ApiKey.objects.filter(pk=self.key.pk).update(is_active=False)
        self.assertEqual(self.client.get("/api/v1/estado/", **self.auth).status_code, 401)

    def test_no_acepta_imagenes(self):
        response = self.client.post("/api/v1/telemetria/", b"\xff\xd8\xff", content_type="image/jpeg", **self.auth)
        self.assertEqual(response.status_code, 415)
