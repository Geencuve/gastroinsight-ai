from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from assistant_chat.services import build_customer_response, build_staff_response
from authentication.models import Profile
from menus.models import Dish, Menu
from operations.models import RestaurantTable, SatisfactionEvaluation, ServiceSession
from sales.models import Order, OrderItem
from venues.models import Venue


class AssistantTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("gerente", password="Test12345!", is_staff=True, is_superuser=True)
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.venue = Venue.objects.create(name="Local de prueba")
        menu = Menu.objects.create(venue=self.venue, name="Carta")
        self.dish = Dish.objects.create(menu=menu, name="Tiramisú", category="Postre", price=Decimal("5990"))
        table = RestaurantTable.objects.create(venue=self.venue, code="X1", capacity=4)
        now = timezone.now()
        session = ServiceSession.objects.create(table=table, started_at=now - timedelta(hours=1), guests_count=2)
        order = Order.objects.create(service_session=session, created_by=self.user)
        OrderItem.objects.create(order=order, dish=self.dish, quantity=2)
        Order.objects.filter(pk=order.pk).update(status=Order.Status.PAID, paid_at=now, total=Decimal("11980"))
        ServiceSession.objects.filter(pk=session.pk).update(status="closed", ended_at=now)
        SatisfactionEvaluation.objects.create(service_session=session, dish=self.dish, rating=5, comment="Excelente")
        SatisfactionEvaluation.objects.create(service_session=session, dish=None, rating=2, comment="Demoraron mucho")

    def test_ventas_responde_con_datos_reales(self):
        text, intent, _ = build_staff_response(self.user, "¿Cuánto vendimos hoy?")
        self.assertEqual(intent, "sales_summary")
        self.assertIn("$11.980", text)
        self.assertNotIn("No existen datos de ventas", text)

    def test_platos_mejor_y_peor_evaluados_no_falla(self):
        text, intent, _ = build_staff_response(self.user, "¿Cuáles son los platos mejor y peor evaluados esta semana?")
        self.assertEqual(intent, "dish_performance")
        self.assertIn("Tiramisú", text)

    def test_comentarios_de_clientes(self):
        text, intent, _ = build_staff_response(self.user, "¿Qué dicen los clientes?")
        self.assertEqual(intent, "customer_comments")
        self.assertIn("Demoraron mucho", text)

    def test_consulta_por_plato_sin_tildes(self):
        text, intent, meta = build_staff_response(self.user, "como le va al tiramisu")
        self.assertEqual(intent, "dish_detail")
        self.assertIn("$5.990", text)
        self.assertTrue(meta["links"])

    def test_pedir_ideas_de_marketing(self):
        _, intent, meta = build_staff_response(self.user, "¿Qué debería promocionar? Dame ideas de marketing")
        self.assertEqual(intent, "advice")
        self.assertIn("links", meta)

    def test_recomendaciones_al_cliente_con_evaluacion_sin_plato(self):
        _, intent, _ = build_customer_response(self.venue, "¿Qué me recomiendan?")
        self.assertEqual(intent, "customer_recommended_dishes")

    def test_widget_devuelve_enlaces(self):
        self.client.force_login(self.user)
        response = self.client.post("/assistant/staff/widget/message/", {"message": "ventas de hoy"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("links", response.json())

    def test_reconoce_periodos(self):
        from assistant_chat.services import get_period_from_message
        self.assertEqual(get_period_from_message("ticket promedio del mes")[2], "este mes")
        self.assertEqual(get_period_from_message("ventas de la semana")[2], "esta semana")
        self.assertEqual(get_period_from_message("ventas del mes pasado")[2], "el mes pasado")
