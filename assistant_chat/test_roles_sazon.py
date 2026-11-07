from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from assistant_chat.services import build_staff_response
from authentication.models import Profile
from cameras.models import Camera
from menus.models import Dish, Menu
from operations.models import InfrastructureReport, RestaurantTable, ServiceSession
from sales.models import Order, OrderItem
from venues.models import Venue


class SazonByRoleTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local de prueba")
        self.table = RestaurantTable.objects.create(venue=self.venue, code="M1", capacity=4)
        self.session = ServiceSession.objects.create(table=self.table, guests_count=2)
        menu = Menu.objects.create(venue=self.venue, name="Carta")
        dish = Dish.objects.create(menu=menu, name="Lomo vetado", category="Fondo", price=Decimal("15990"))
        self.order = Order.objects.create(service_session=self.session, created_by=self._user("base", Profile.Role.OPERATOR))
        OrderItem.objects.create(order=self.order, dish=dish, quantity=1)
        Order.objects.filter(pk=self.order.pk).update(status=Order.Status.CONFIRMED,
                                                      confirmed_at=timezone.now() - timedelta(minutes=5))

    def _user(self, name, role):
        user = User.objects.create_user(name, password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(self.venue)
        return user

    def test_cocina_consulta_comandas_y_no_ventas(self):
        cook = self._user("cocinero", Profile.Role.KITCHEN)
        text, intent, meta = build_staff_response(cook, "¿Cómo va la cocina?")
        self.assertEqual(intent, "kitchen_queue")
        self.assertIn("1 pendientes", text)
        self.assertTrue(meta["metrics"])
        text, intent, _ = build_staff_response(cook, "¿Cuál es el ticket promedio?")
        self.assertEqual(intent, "out_of_scope")
        self.assertIn("corresponde a otro rol", text)

    def test_mesero_recibe_el_estado_de_la_sala_por_defecto(self):
        waiter = self._user("mesero", Profile.Role.WAITER)
        text, intent, _ = build_staff_response(waiter, "hola")
        self.assertEqual(intent, "floor_status")
        self.assertIn("Sala", text)
        text, intent, _ = build_staff_response(waiter, "¿qué puedes hacer?")
        self.assertEqual(intent, "role_help")
        self.assertIn("mesero", text)

    def test_caja_consulta_el_termometro(self):
        cashier = self._user("cajera", Profile.Role.CASHIER)
        text, intent, _ = build_staff_response(cashier, "¿Cómo está el termómetro de caja?")
        self.assertEqual(intent, "cashier_status")
        self.assertIn("Mesa M1", text)

    def test_supervisor_consulta_mediciones_por_camara_e_infraestructura(self):
        supervisor = self._user("supervisora", Profile.Role.SUPERVISOR)
        camera = Camera.objects.create(venue=self.venue, name="Cam salón", source="demo",
                                       source_type=Camera.SourceType.DEMO, table=self.table)
        analysis = AnalysisSession.objects.create(camera=camera, status="running")
        DetectionEvent.objects.create(session=analysis, faces_count=2, table=self.table, experience_index=Decimal("70"),
                                      persons_detected=Decimal("3"), processing_time_ms=30)
        text, intent, meta = build_staff_response(supervisor, "¿Cómo están las mediciones por cámara?")
        self.assertEqual(intent, "camera_metrics")
        self.assertIn("Cam salón", text)
        self.assertIn("YOLO26", text)
        InfrastructureReport.objects.create(venue=self.venue, area="restrooms", description="Falta papel")
        text, intent, _ = build_staff_response(supervisor, "¿Cómo está la infraestructura?")
        self.assertEqual(intent, "infrastructure")
        self.assertIn("Falta papel", text)

    def test_interfaz_de_sazon_se_adapta_al_rol(self):
        self.client.force_login(self._user("barman", Profile.Role.BAR))
        response = self.client.get("/assistant/staff/")
        self.assertContains(response, "Bebidas pendientes")
        self.assertNotContains(response, "Ventas de la semana")
