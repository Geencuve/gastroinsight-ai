from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from authentication.models import Profile
from cameras.models import Camera
from menus.models import Dish, Menu
from operations.models import RestaurantTable, ServiceSession
from sales.models import Order, OrderItem
from sales.services.kitchen import acceptance, queue, station_for
from venues.models import Venue


class KitchenAndBarTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local de prueba")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="M1", capacity=4)
        self.user = User.objects.create_user("jefe", password="Test12345!", is_superuser=True, is_staff=True)
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.session = ServiceSession.objects.create(table=self.table, guests_count=2, created_by=self.user)
        menu = Menu.objects.create(venue=self.venue, name="Carta")
        self.lomo = Dish.objects.create(menu=menu, name="Lomo vetado", category="Fondo", price=Decimal("15990"))
        self.pisco = Dish.objects.create(menu=menu, name="Pisco sour", category="Bebida", price=Decimal("5490"))
        self.order = Order.objects.create(service_session=self.session, created_by=self.user)
        self.food = OrderItem.objects.create(order=self.order, dish=self.lomo, quantity=2)
        self.drink = OrderItem.objects.create(order=self.order, dish=self.pisco, quantity=1)
        Order.objects.filter(pk=self.order.pk).update(status=Order.Status.CONFIRMED,
                                                      confirmed_at=timezone.now() - timedelta(minutes=12))
        self.venues = Venue.objects.all()

    def test_estacion_segun_categoria(self):
        self.assertEqual(station_for(self.food), "cocina")
        self.assertEqual(station_for(self.drink), "barra")

    def test_cocina_avanza_estados_y_avisa_a_la_sala(self):
        kitchen = queue(self.venues, "cocina")
        pending = kitchen["columns"][0]["cards"]
        self.assertEqual([i.dish_name for i in pending[0]["items"]], ["Lomo vetado"])
        self.assertEqual(pending[0]["level"], "warn")
        self.client.force_login(self.user)
        self.client.post("/cocina/avanzar/", {"ids": str(self.food.id)})
        self.client.post("/cocina/avanzar/", {"ids": str(self.food.id)})
        self.food.refresh_from_db()
        self.assertEqual(self.food.prep_status, "ready")
        self.assertIsNotNone(self.food.prep_started_at)
        self.assertContains(self.client.get("/sala/"), "listos para servir")
        self.client.post(f"/sala/atencion/{self.session.id}/entregar/")
        self.food.refresh_from_db()
        self.assertEqual(self.food.prep_status, "delivered")

    def test_barra_usa_sus_propios_tiempos(self):
        bar = queue(self.venues, "barra")
        card = bar["columns"][0]["cards"][0]
        self.assertEqual([i.dish_name for i in card["items"]], ["Pisco sour"])
        self.assertEqual(card["level"], "late")

    def test_aceptacion_mide_la_variacion_del_ibe(self):
        delivered = timezone.now() - timedelta(minutes=30)
        OrderItem.objects.filter(pk=self.food.pk).update(prep_status="delivered", delivered_at=delivered)
        camera = Camera.objects.create(venue=self.venue, name="Cam", source="demo",
                                       source_type=Camera.SourceType.DEMO, table=self.table)
        analysis = AnalysisSession.objects.create(camera=camera, status="completed")
        for minutes, valence in ((-10, "-0.2"), (-5, "-0.2"), (5, "0.4"), (10, "0.4")):
            event = DetectionEvent.objects.create(session=analysis, faces_count=2, table=self.table,
                                                  service_session=self.session, valence=Decimal(valence))
            DetectionEvent.objects.filter(pk=event.pk).update(detected_at=delivered + timedelta(minutes=minutes))
        row = next(r for r in acceptance(self.venues, "cocina") if r["name"] == "Lomo vetado")
        self.assertAlmostEqual(row["ibe_delta"], 0.6, places=2)
        self.assertEqual(row["units"], 2)

    def test_cocina_y_barra_llegan_a_su_pantalla(self):
        for role, home, blocked in ((Profile.Role.KITCHEN, "/cocina/", "/barra/"), (Profile.Role.BAR, "/barra/", "/cocina/")):
            user = User.objects.create_user(f"u_{role}", password="Test12345!")
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = role
            profile.save()
            profile.venues.add(self.venue)
            self.client.force_login(user)
            self.assertRedirects(self.client.get("/"), home, fetch_redirect_response=False)
            self.assertEqual(self.client.get(home).status_code, 200)
            self.assertEqual(self.client.get(blocked).status_code, 403)
