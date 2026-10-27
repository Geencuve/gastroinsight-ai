import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from assistant_chat.models import ChatConversation, ChatMessage
from menus.models import Dish, Menu
from operations.models import RestaurantTable, SatisfactionEvaluation, ServiceSession
from sales.models import Order, OrderItem
from venues.models import Venue

TAG = "Generado automáticamente para demo."

EXTRA_DISHES = [
    ("Empanadas de pino (3)", "Entrada", 6490),
    ("Ceviche de reineta", "Entrada", 8990),
    ("Tabla de quesos", "Entrada", 9990),
    ("Lomo vetado con papas rústicas", "Fondo", 15990),
    ("Pastel de choclo", "Fondo", 9490),
    ("Pollo al limón con arroz", "Fondo", 8990),
    ("Leche asada", "Postre", 3990),
    ("Pisco sour", "Bebida", 5490),
    ("Jugo natural", "Bebida", 3490),
    ("Café espresso", "Bebida", 2490),
]
EXTRA_TABLES = [
    ("M03", 4, "Salón principal"),
    ("M04", 4, "Salón principal"),
    ("T02", 4, "Terraza"),
    ("B01", 2, "Barra"),
]
COMMENTS = {
    5: ["Excelente atención, volveremos.", "Todo muy rico y rápido.", "Los platos llegaron perfectos."],
    4: ["Muy buena comida.", "Buen servicio, algo de espera.", "Rico y porciones generosas."],
    3: ["Correcto, nada especial.", "La comida bien, el servicio lento."],
    2: ["Demoraron mucho en traer los platos.", "El plato llegó frío."],
    1: ["Mala experiencia, mucha espera."],
}
DRINK_COMMENTS = {
    5: ["Excelente coctelería.", "Muy refrescante, la recomiendo."],
    4: ["Buena bebida, bien preparada.", "Rica, aunque tardó un poco."],
    3: ["Correcta, nada especial."],
    2: ["Llegó tibia y con poco hielo.", "Muy dulce para mi gusto."],
    1: ["La bebida no estaba bien preparada."],
}
PAYMENT_METHODS = ["DEBIT", "CREDIT", "CASH", "TRANSFER"]
PAYMENT_WEIGHTS = [45, 25, 20, 10]
RATINGS = [5, 5, 5, 4, 4, 4, 4, 3, 3, 2, 1]


def clp(value):
    return "$" + f"{int(value or 0):,}".replace(",", ".")


def at(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


class Command(BaseCommand):
    help = "Genera historial demo de ventas, evaluaciones y conversaciones del asistente."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=21, help="Días de historial (por defecto 21).")
        parser.add_argument("--reset", action="store_true", help="Borra los datos demo generados y los vuelve a crear.")

    @transaction.atomic
    def handle(self, *args, **options):
        self.rng = random.Random(2026)
        venue = Venue.objects.filter(name="Restaurante Demo Santiago").first()
        if venue is None:
            raise CommandError("Primero ejecuta: python manage.py seed_demo_data")
        self.operator = User.objects.get(username="operador_demo")
        self.admin = User.objects.get(username="admin_demo")
        menu = Menu.objects.get(venue=venue, name="Carta principal")

        if options["reset"]:
            self.reset()
        elif ServiceSession.objects.filter(notes=TAG).exists():
            self.stdout.write(self.style.WARNING("Ya existen datos demo de ventas. Usa --reset para regenerarlos."))
            return

        for name, category, price in EXTRA_DISHES:
            Dish.objects.get_or_create(
                menu=menu, name=name,
                defaults={"category": category, "price": Decimal(price), "is_available": True},
            )
        for code, capacity, zone in EXTRA_TABLES:
            RestaurantTable.objects.get_or_create(
                venue=venue, code=code,
                defaults={"capacity": capacity, "zone_name": zone, "is_active": True},
            )

        self.by_category = {}
        for dish in Dish.objects.filter(menu=menu, is_available=True):
            self.by_category.setdefault(dish.category, []).append(dish)

        tables = RestaurantTable.objects.filter(venue=venue, is_active=True)
        busy = set(
            ServiceSession.objects.filter(table__in=tables, status=ServiceSession.Status.OPEN)
            .values_list("table_id", flat=True)
        )
        self.free_tables = [t for t in tables if t.id not in busy]
        if not self.free_tables:
            raise CommandError("Todas las mesas tienen una sesión abierta. Ciérralas antes de ejecutar.")

        self.stats = {"sesiones": 0, "pagados": 0, "anulados": 0, "evaluaciones": 0, "ingresos": Decimal("0")}
        today = timezone.localdate()

        for days_back in range(options["days"], 0, -1):
            day = today - timedelta(days=days_back)
            weekend = day.weekday() >= 4
            count = self.rng.randint(7, 11) if weekend else self.rng.randint(3, 6)
            hours = [13, 13, 14, 14, 20, 20, 21, 21, 22] if weekend else [13, 13, 14, 20, 21]
            for _ in range(count):
                start = at(day, self.rng.choice(hours), self.rng.choice([0, 10, 20, 30, 40, 50]))
                self.closed_session(self.rng.choice(self.free_tables), start)

        now = timezone.localtime()
        for hour in (12, 13, 13, 14, 20):
            if hour + 2 <= now.hour:
                start = at(today, hour, self.rng.choice([0, 15, 30, 45]))
                self.closed_session(self.rng.choice(self.free_tables), start)

        live_tables = self.rng.sample(self.free_tables, min(3, len(self.free_tables)))
        for index, table in enumerate(live_tables):
            self.open_session(table, now - timedelta(minutes=15 + 20 * index), confirm=(index == 0))

        self.create_conversations(venue, today)
        self.polish_seed_evaluations()

        s = self.stats
        self.stdout.write(self.style.SUCCESS("Datos demo de ventas creados correctamente."))
        self.stdout.write(f" - Sesiones cerradas: {s['sesiones']}")
        self.stdout.write(f" - Pedidos pagados: {s['pagados']} | anulados: {s['anulados']}")
        self.stdout.write(f" - Ventas totales: {clp(s['ingresos'])}")
        self.stdout.write(f" - Evaluaciones: {s['evaluaciones']}")
        self.stdout.write(f" - Mesas con atención en curso: {len(live_tables)}")

    def pick_dishes(self, guests):
        counts = {}

        def add(category):
            options = self.by_category.get(category)
            if options:
                dish = self.rng.choice(options)
                counts[dish] = counts.get(dish, 0) + 1

        for _ in range(guests):
            add("Fondo")
            add("Bebida")
            if self.rng.random() < 0.4:
                add("Postre")
        if self.rng.random() < 0.6:
            add("Entrada")
        return list(counts.items())

    def closed_session(self, table, start):
        rng = self.rng
        guests = rng.randint(1, table.capacity)
        session = ServiceSession.objects.create(
            table=table, started_at=start, guests_count=guests,
            created_by=self.operator, notes=TAG,
        )
        order = Order.objects.create(service_session=session, created_by=self.operator, notes=TAG)
        chosen = self.pick_dishes(guests)
        for dish, quantity in chosen:
            OrderItem.objects.create(order=order, dish=dish, quantity=quantity)
        order.refresh_from_db()

        end = start + timedelta(minutes=rng.randint(45, 110))
        dates = {"opened_at": start + timedelta(minutes=2)}

        if rng.random() < 0.05:
            order.cancel()
            dates["cancelled_at"] = start + timedelta(minutes=10)
            self.stats["anulados"] += 1
        else:
            if rng.random() < 0.15:
                order.discount_amount = (order.subtotal * Decimal("0.10")).quantize(Decimal("1"))
                order.save(update_fields=["discount_amount", "updated_at"])
                order.recalculate_totals()
            order.confirm()
            order.mark_as_paid(rng.choices(PAYMENT_METHODS, weights=PAYMENT_WEIGHTS)[0])
            dates["confirmed_at"] = start + timedelta(minutes=rng.randint(5, 15))
            dates["paid_at"] = end - timedelta(minutes=3)
            self.stats["pagados"] += 1
            self.stats["ingresos"] += order.total

            if rng.random() < 0.45:
                dish, _ = rng.choice(chosen)
                rating = rng.choice(RATINGS)
                evaluation = SatisfactionEvaluation.objects.create(
                    service_session=session, dish=dish, rating=rating,
                    comment=self.comment_for(rating, dish), registered_by=self.operator,
                )
                SatisfactionEvaluation.objects.filter(pk=evaluation.pk).update(
                    created_at=end - timedelta(minutes=5)
                )
                self.stats["evaluaciones"] += 1

        Order.objects.filter(pk=order.pk).update(**dates)
        OrderItem.objects.filter(order=order).update(created_at=start + timedelta(minutes=4))
        session.close(self.operator)
        ServiceSession.objects.filter(pk=session.pk).update(ended_at=end)
        self.stats["sesiones"] += 1

    def open_session(self, table, start, confirm=False):
        session = ServiceSession.objects.create(
            table=table, started_at=start, guests_count=min(2, table.capacity),
            created_by=self.operator, notes=TAG,
        )
        order = Order.objects.create(service_session=session, created_by=self.operator, notes=TAG)
        for dish, quantity in self.pick_dishes(session.guests_count):
            OrderItem.objects.create(order=order, dish=dish, quantity=quantity)
        if confirm:
            order.confirm()
        Order.objects.filter(pk=order.pk).update(opened_at=start + timedelta(minutes=2))

    def create_conversations(self, venue, today):
        since = at(today - timedelta(days=7), 0)
        paid = Order.objects.filter(
            service_session__table__venue=venue, status=Order.Status.PAID, paid_at__gte=since,
        )
        summary = paid.aggregate(total=Sum("total"), count=Count("id"))
        top = list(
            OrderItem.objects.filter(order__in=paid)
            .values("dish_name").annotate(units=Sum("quantity")).order_by("-units")[:3]
        )
        rating = SatisfactionEvaluation.objects.filter(
            service_session__table__venue=venue, created_at__gte=since,
        ).aggregate(avg=Avg("rating"), n=Count("id"))

        top_text = ", ".join(f"{t['dish_name']} ({t['units']} unidades)" for t in top) or "sin datos"
        avg_text = f"{rating['avg']:.1f}" if rating["avg"] else "sin datos"

        conversations = [
            (ChatConversation.Audience.STAFF, self.admin, "Resumen de ventas semanal", 1, [
                ("USER", "¿Cuánto vendimos en los últimos 7 días?", ""),
                ("ASSISTANT", f"En los últimos 7 días se registraron {summary['count'] or 0} pedidos pagados, con ventas por {clp(summary['total'])}.", "sales_summary"),
                ("USER", "¿Cuáles fueron los platos más vendidos?", ""),
                ("ASSISTANT", f"Los platos más vendidos fueron: {top_text}.", "top_dishes"),
            ]),
            (ChatConversation.Audience.STAFF, self.operator, "Satisfacción de clientes", 0, [
                ("USER", "¿Cómo va la satisfacción de los clientes esta semana?", ""),
                ("ASSISTANT", f"La valoración promedio de los últimos 7 días es {avg_text} de 5, con {rating['n']} evaluaciones voluntarias registradas.", "satisfaction_summary"),
            ]),
            (ChatConversation.Audience.CUSTOMER, None, "Consulta de cliente", 2, [
                ("USER", "Hola, ¿tienen opciones vegetarianas?", ""),
                ("ASSISTANT", "¡Hola! Sí, te recomendamos el Risotto de hongos y la Tabla de quesos. ¿Te gustaría conocer los postres?", "menu_info"),
                ("USER", "Sí, ¿qué postres tienen?", ""),
                ("ASSISTANT", "Tenemos Tiramisú y Leche asada, ambos disponibles hoy.", "menu_info"),
            ]),
        ]

        for audience, user, title, days_back, messages in conversations:
            moment = timezone.localtime() - timedelta(days=days_back, hours=1)
            conversation = ChatConversation.objects.create(
                user=user, venue=venue, audience=audience, title=title,
            )
            for i, (sender, content, intent) in enumerate(messages):
                message = ChatMessage.objects.create(
                    conversation=conversation, sender=sender, content=content,
                    intent=intent, metadata={"demo": True},
                )
                ChatMessage.objects.filter(pk=message.pk).update(created_at=moment + timedelta(seconds=30 * i))
            ChatConversation.objects.filter(pk=conversation.pk).update(
                created_at=moment, updated_at=moment + timedelta(seconds=30 * len(messages)),
            )

    def comment_for(self, rating, dish):
        pool = DRINK_COMMENTS if dish is not None and dish.category == "Bebida" else COMMENTS
        return self.rng.choice(pool[rating])

    def polish_seed_evaluations(self):
        """Comentarios realistas y fechas coherentes para las evaluaciones del seed base."""
        for evaluation in SatisfactionEvaluation.objects.filter(
            comment="Evaluación de demostración."
        ).select_related("service_session", "dish"):
            session = evaluation.service_session
            moment = session.ended_at or session.started_at
            SatisfactionEvaluation.objects.filter(pk=evaluation.pk).update(
                comment=self.comment_for(evaluation.rating, evaluation.dish),
                created_at=moment - timedelta(minutes=5),
            )

    def reset(self):
        sessions = ServiceSession.objects.filter(notes=TAG)
        SatisfactionEvaluation.objects.filter(service_session__in=sessions).delete()
        orders = Order.objects.filter(service_session__in=sessions)
        OrderItem.objects.filter(order__in=orders).delete()
        orders.delete()
        deleted = sessions.count()
        sessions.delete()
        ids = set(ChatMessage.objects.filter(metadata__demo=True).values_list("conversation_id", flat=True))
        ChatConversation.objects.filter(id__in=ids).delete()
        self.stdout.write(f"Reset: {deleted} sesiones demo eliminadas.")
