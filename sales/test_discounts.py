from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from menus.models import Dish, Menu
from operations.models import RestaurantTable, ServiceSession
from sales.models import Order, OrderItem
from venues.models import Venue


class DiscountRecalculationTests(TestCase):
    """El descuento se ajusta si el subtotal baja al eliminar ítems."""

    def setUp(self):
        user = User.objects.create_user("tester", password="Test12345!")
        venue = Venue.objects.create(name="Local de prueba")
        menu = Menu.objects.create(venue=venue, name="Carta de prueba")
        dish_a = Dish.objects.create(menu=menu, name="Plato A", price=Decimal("10000"))
        dish_b = Dish.objects.create(menu=menu, name="Plato B", price=Decimal("10000"))
        table = RestaurantTable.objects.create(venue=venue, code="X1", capacity=4)
        session = ServiceSession.objects.create(table=table, guests_count=2, created_by=user)
        self.order = Order.objects.create(service_session=session, created_by=user)
        OrderItem.objects.create(order=self.order, dish=dish_a, quantity=1)
        self.item_b = OrderItem.objects.create(order=self.order, dish=dish_b, quantity=1)
        self.order.discount_amount = Decimal("15000")
        self.order.save(update_fields=["discount_amount", "updated_at"])
        self.order.recalculate_totals()

    def test_descuento_valido_se_mantiene(self):
        self.order.refresh_from_db()
        self.assertEqual(self.order.subtotal, Decimal("20000"))
        self.assertEqual(self.order.discount_amount, Decimal("15000"))
        self.assertEqual(self.order.total, Decimal("5000"))

    def test_eliminar_item_ajusta_descuento_sin_error(self):
        self.item_b.delete()
        self.order.refresh_from_db()
        self.assertEqual(self.order.subtotal, Decimal("10000"))
        self.assertEqual(self.order.discount_amount, Decimal("10000"))
        self.assertEqual(self.order.total, Decimal("0"))

    def test_eliminar_todos_los_items_deja_todo_en_cero(self):
        self.order.items.all().delete()
        self.order.refresh_from_db()
        self.assertEqual(self.order.subtotal, Decimal("0"))
        self.assertEqual(self.order.discount_amount, Decimal("0"))
        self.assertEqual(self.order.total, Decimal("0"))
