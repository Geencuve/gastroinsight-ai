from decimal import Decimal

import numpy as np
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from ai_vision.services.hud import render_hud
from authentication.models import Profile
from menus.models import Dish, Menu
from monitoring.models import AuditLog
from operations.models import RestaurantTable, ServiceSession
from sales.models import Order, OrderItem
from venues.models import Venue


class HudAndFiltersTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local de prueba")
        self.admin = User.objects.create_user("jefa", password="Test12345!", is_superuser=True, is_staff=True)
        profile, _ = Profile.objects.get_or_create(user=self.admin)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()

    def test_hud_compone_el_fotograma_con_el_panel(self):
        frame = np.zeros((480, 640, 3), np.uint8)
        result = {"faces_count": 1, "processing_time_ms": 28,
                  "faces": [{"box": {"x": 100, "y": 120, "width": 80, "height": 80}, "emotion": "happy",
                             "emotion_confidence": 0.82, "looking_away": False}],
                  "scene": {"persons": 2, "tables": 1, "boxes": [[0.5, 0.5, 0.3, 0.2, "t"], [0.3, 0.5, 0.1, 0.3, "p"]]}}
        info = {"camera": "Webcam", "table": "M01", "events": 3, "frame": 90, "elapsed": 4.0,
                "summary": {"valence": 0.3, "attention_seeking": 0.1, "activity_level": 22}}
        composed = render_hud(frame, result, info)
        self.assertEqual(composed.shape, (560, 640 + 330, 3))
        self.assertEqual(composed.dtype, np.uint8)
        self.assertGreater(int(composed[:, 640:].mean()), 0)

    def test_auditoria_filtra_y_exporta(self):
        AuditLog.objects.create(user=self.admin, action=AuditLog.Action.LOGIN, module="authentication", description="Ingreso de prueba")
        AuditLog.objects.create(user=self.admin, action=AuditLog.Action.CREATE, module="sales", description="Pedido creado")
        self.client.force_login(self.admin)
        response = self.client.get("/monitoring/audit/", {"modulo": "sales"})
        self.assertContains(response, "Pedido creado")
        self.assertNotContains(response, "Ingreso de prueba")
        csv_response = self.client.get("/monitoring/audit/", {"q": "Ingreso", "formato": "csv"})
        content = csv_response.content.decode("utf-8-sig")
        self.assertIn("Ingreso de prueba", content)
        self.assertNotIn("Pedido creado", content)

    def test_explorador_de_ventas_filtra_por_plato_y_mesa(self):
        table = RestaurantTable.objects.create(venue=self.venue, code="M1", capacity=4)
        other = RestaurantTable.objects.create(venue=self.venue, code="M2", capacity=4)
        menu = Menu.objects.create(venue=self.venue, name="Carta")
        lomo = Dish.objects.create(menu=menu, name="Lomo vetado", category="Fondo", price=Decimal("15990"))
        pisco = Dish.objects.create(menu=menu, name="Pisco sour", category="Bebida", price=Decimal("5490"))
        for t, dish in ((table, lomo), (other, pisco)):
            session = ServiceSession.objects.create(table=t, guests_count=2)
            order = Order.objects.create(service_session=session, created_by=self.admin)
            OrderItem.objects.create(order=order, dish=dish, quantity=1)
            Order.objects.filter(pk=order.pk).update(status=Order.Status.PAID, paid_at=timezone.now())
        self.client.force_login(self.admin)
        response = self.client.get("/reports/explorar/", {"plato": "lomo"})
        self.assertContains(response, "Lomo vetado")
        self.assertNotContains(response, "Pisco sour")
        response = self.client.get("/reports/explorar/", {"mesa": "M2", "formato": "csv"})
        self.assertIn("Pisco sour", response.content.decode("utf-8-sig"))
