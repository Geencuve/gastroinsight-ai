"""
Sugerencias de negocio generadas a partir de los datos: oportunidades de venta,
ideas de marketing y mejoras en la experiencia. Los impactos son estimaciones
simples para orientar decisiones, no proyecciones financieras.
"""
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from itertools import combinations
from statistics import median

from urllib.parse import urlencode

from django.db.models import Avg, Count, Q, Sum
from django.urls import reverse
from django.utils import timezone

from analytics.services.correlation import build_dataset
from menus.models import Dish
from monitoring.models import Incident
from operations.models import SatisfactionEvaluation, ServiceSession
from sales.models import Order, OrderItem

WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábados", "domingos"]
PARTNER_CATEGORIES = {"Bebida", "Postre", "Entrada"}


def clp(value):
    return "$" + f"{int(round(float(value or 0))):,}".replace(",", ".")


def _start(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def _item(icon, title, why, action, url_name=None, impact=None, score=0, promo=None):
    return {
        "icon": icon, "title": title, "why": why, "action": action,
        "impact": impact, "url": reverse(url_name) if url_name else None, "score": score,
        "promo_url": (reverse("core:promo_generator") + "?" + urlencode(promo)) if promo else None,
    }


def build_home_summary(venues, today=None):
    """Indicadores rápidos del día."""
    today = today or timezone.localdate()
    start, end = _start(today), _start(today + timedelta(days=1))
    orders = Order.objects.filter(service_session__table__venue__in=venues)
    sales = orders.filter(status=Order.Status.PAID, paid_at__gte=start, paid_at__lt=end).aggregate(
        total=Sum("total"), count=Count("id"),
    )
    ratings = SatisfactionEvaluation.objects.filter(
        service_session__table__venue__in=venues, created_at__gte=_start(today - timedelta(days=6)),
    ).aggregate(count=Count("id"), happy=Count("id", filter=Q(rating__gte=4)))
    count = sales["count"] or 0
    return {
        "sales_today": sales["total"] or 0,
        "orders_today": count,
        "average_ticket": (sales["total"] / count) if count else 0,
        "open_tables": ServiceSession.objects.filter(
            table__venue__in=venues, status=ServiceSession.Status.OPEN,
        ).count(),
        "pending_orders": orders.filter(status__in=[Order.Status.OPEN, Order.Status.CONFIRMED]).count(),
        "satisfied_pct": (100 * ratings["happy"] / ratings["count"]) if ratings["count"] else None,
        "ratings_count": ratings["count"],
    }


def build_insights(venues, today=None, per_section=3):
    today = today or timezone.localdate()
    now = timezone.now()
    tomorrow = _start(today + timedelta(days=1))
    week_start = _start(today - timedelta(days=6))
    previous_start = _start(today - timedelta(days=13))
    window_start = _start(today - timedelta(days=27))
    sections = {"now": [], "ventas": [], "marketing": [], "servicio": []}
    synthetic = False

    orders = Order.objects.filter(service_session__table__venue__in=venues)
    paid = orders.filter(status=Order.Status.PAID)
    paid_window = paid.filter(paid_at__gte=window_start, paid_at__lt=tomorrow)

    # ================= Para atender ahora =================
    long_open = list(
        ServiceSession.objects.filter(
            table__venue__in=venues, status=ServiceSession.Status.OPEN,
            started_at__lt=now - timedelta(minutes=120),
        ).values_list("table__code", flat=True)
    )
    if long_open:
        sections["now"].append(_item(
            "⏰", f"Mesas abiertas hace más de 2 horas: {', '.join(sorted(set(long_open)))}",
            "", "Revisa si falta cobrar o si la atención se está demorando.", "operations:session_list", 100,
        ))
    stale = orders.filter(status=Order.Status.CONFIRMED, confirmed_at__lt=now - timedelta(minutes=45)).count()
    if stale:
        sections["now"].append(_item(
            "🧾", f"{stale} pedido{'s' if stale != 1 else ''} esperando pago hace más de 45 minutos",
            "", "Registra el pago o anula lo que ya no corresponda.", "sales:order_list", 95,
        ))
    from ai_vision.services.live import build_live_state

    for alert in build_live_state(venues)["alerts"][:3]:
        sections["now"].append(_item(
            "👀" if "atención" in alert["text"] else "📉", f"Mesa {alert['table']}: {alert['text']}", "",
            "Acércate a la mesa y revisa su atención.", "ai_vision:monitor", 98,
        ))
    incidents = Incident.objects.filter(venue__in=venues, status=Incident.Status.OPEN).count()
    if incidents:
        sections["now"].append(_item(
            "🛠️", f"{incidents} incidencia{'s' if incidents != 1 else ''} técnica{'s' if incidents != 1 else ''} sin revisar",
            "", "Revísalas para asegurar la calidad de los datos.", "monitoring:incident_list", 90,
        ))

    # ================= Datos base de las últimas 4 semanas =================
    order_dishes = defaultdict(set)
    dish_names, dish_categories = {}, {}
    units, revenue = Counter(), Counter()
    for order_id, dish_id, name, category, quantity, line_total in OrderItem.objects.filter(
        order__in=paid_window,
    ).values_list("order_id", "dish_id", "dish_name", "dish__category", "quantity", "line_total"):
        order_dishes[order_id].add(dish_id)
        dish_names[dish_id], dish_categories[dish_id] = name, category
        units[dish_id] += quantity
        revenue[dish_id] += float(line_total)
    n_orders = len(order_dishes)

    first_sale = paid_window.order_by("paid_at").values_list("paid_at", flat=True).first()
    days_with_data = (today - timezone.localtime(first_sale).date()).days + 1 if first_sale else 0
    weeks = max(days_with_data / 7, 1)

    ratings_by_dish = {
        row["dish_id"]: row
        for row in SatisfactionEvaluation.objects.filter(
            service_session__table__venue__in=venues, created_at__gte=window_start, dish__isnull=False,
        ).values("dish_id").annotate(avg=Avg("rating"), count=Count("id"))
    }

    # ================= 💰 Oportunidades de venta =================
    week = paid.filter(paid_at__gte=week_start, paid_at__lt=tomorrow).aggregate(total=Sum("total"))["total"] or 0
    previous = paid.filter(paid_at__gte=previous_start, paid_at__lt=week_start).aggregate(total=Sum("total"))["total"] or 0
    if previous:
        change = 100 * (float(week) - float(previous)) / float(previous)
        if change <= -10:
            sections["ventas"].append(_item(
                "📉", f"Esta semana vendiste {abs(change):.0f}% menos que la anterior",
                f"{clp(week)} en los últimos 7 días, frente a {clp(previous)} la semana previa.",
                "Activa una promoción de reactivación: un beneficio para la próxima visita o una oferta en tus redes.",
                "reports:list", score=80,
            ))
        elif change >= 10:
            sections["ventas"].append(_item(
                "📈", f"Tus ventas crecieron {change:.0f}% esta semana",
                f"{clp(week)} en los últimos 7 días, frente a {clp(previous)} la semana previa.",
                "Revisa qué platos y días impulsaron el alza para repetirlo.", "reports:list", score=30,
            ))

    if n_orders >= 10:
        weekly_orders = n_orders / weeks
        for category, icon, label, action, score in (
            ("Postre", "🍰", "pide postre",
             "Ofrece la carta de postres al retirar los platos de fondo, o sugiere un postre para compartir.", 70),
            ("Entrada", "🥟", "pide entrada",
             "Sugiere una entrada para compartir mientras esperan el plato de fondo.", 60),
        ):
            with_category = sum(1 for dishes in order_dishes.values()
                                if any(dish_categories.get(d) == category for d in dishes))
            rate = 100 * with_category / n_orders
            price = Dish.objects.filter(
                menu__venue__in=venues, category=category, is_available=True,
            ).aggregate(avg=Avg("price"))["avg"]
            if price and rate < 50:
                gain = 0.10 * weekly_orders * float(price)
                sections["ventas"].append(_item(
                    icon, f"Solo el {rate:.0f}% de las mesas {label}",
                    f"De {n_orders} pedidos en las últimas semanas, {with_category} incluyeron {category.lower()}.",
                    action, "menus:list",
                    impact=f"+{clp(gain)} por semana si 1 de cada 10 mesas más lo pide", score=score,
                ))

        sold_units = {dish_id: units.get(dish_id, 0) for dish_id in Dish.objects.filter(
            menu__venue__in=venues, menu__is_active=True, is_available=True,
        ).values_list("id", flat=True)}
        slow = [dish_id for dish_id, count in sold_units.items() if count <= 2]
        if slow:
            names = list(Dish.objects.filter(id__in=slow).values_list("name", flat=True)[:4])
            sections["ventas"].append(_item(
                "🗒️", f"{len(slow)} plato{'s' if len(slow) != 1 else ''} casi no se vende{'n' if len(slow) != 1 else ''}",
                ", ".join(names) + ": 2 unidades o menos en las últimas semanas.",
                "Prueba una promoción de lanzamiento o reemplázalos por una novedad de temporada.",
                "menus:list", score=40,
            ))

    # ================= 📣 Ideas de marketing =================
    if n_orders >= 10:
        # Combo: qué se pide junto con cada plato de fondo
        anchor_count, pair_count = Counter(), Counter()
        for dishes in order_dishes.values():
            for dish in dishes:
                anchor_count[dish] += 1
            for a, b in combinations(dishes, 2):
                pair_count[(a, b)] += 1
                pair_count[(b, a)] += 1
        best = None
        for (anchor, partner), together in pair_count.items():
            if dish_categories.get(anchor) != "Fondo" or dish_categories.get(partner) not in PARTNER_CATEGORIES:
                continue
            if together < 5:
                continue
            confidence = together / anchor_count[anchor]
            if best is None or confidence > best[2]:
                best = (anchor, partner, confidence)
        if best and best[2] >= 0.25:
            anchor, partner, confidence = best
            sections["marketing"].append(_item(
                "🤝", f"Combo sugerido: {dish_names[anchor]} + {dish_names[partner]}",
                f"El {100 * confidence:.0f}% de quienes piden {dish_names[anchor]} también pide {dish_names[partner]}.",
                "Ofrécelos juntos con un pequeño descuento y muéstralo en la carta y en redes sociales.",
                "menus:list", score=65, promo={"tipo": "combo", "plato": anchor, "plato2": partner},
            ))

        # Día más flojo de la semana
        by_weekday = Counter()
        for paid_at, total in paid_window.values_list("paid_at", "total"):
            by_weekday[timezone.localtime(paid_at).weekday()] += float(total)
        start_day = today - timedelta(days=days_with_data - 1)
        occurrences = Counter((start_day + timedelta(days=i)).weekday() for i in range(days_with_data))
        averages = {wd: by_weekday[wd] / occurrences[wd] for wd in occurrences if occurrences[wd]}
        if len(averages) == 7:
            typical = sum(averages.values()) / 7
            weakest = min(averages, key=averages.get)
            if typical and averages[weakest] < 0.7 * typical:
                gain = 0.8 * typical - averages[weakest]
                day = WEEKDAYS[weakest]
                sections["marketing"].append(_item(
                    "📅", f"Los {day} son tu día más flojo",
                    f"Vendes en promedio {clp(averages[weakest])} esos días, frente a {clp(typical)} de un día típico.",
                    f"Crea una promoción exclusiva para los {day} (menú del día, 2x1 en bebidas) y anúnciala en redes el día anterior.",
                    "reports:list",
                    impact=f"+{clp(gain)} por semana si ese día llega al 80% de un día típico", score=75, promo={"tipo": "dia", "dia": weakest},
                ))

        # Tardes vacías entre almuerzo y cena
        by_hour = Counter()
        for paid_at, total in paid_window.values_list("paid_at", "total"):
            by_hour[timezone.localtime(paid_at).hour] += float(total)
        total_sales = sum(by_hour.values())
        afternoon = sum(by_hour[h] for h in (16, 17, 18))
        has_lunch = any(by_hour[h] for h in range(12, 16))
        has_dinner = any(by_hour[h] for h in range(20, 24))
        if total_sales and has_lunch and has_dinner and afternoon / total_sales < 0.05:
            sections["marketing"].append(_item(
                "🍹", "Las tardes, de 16:00 a 19:00, están casi vacías",
                f"Solo el {100 * afternoon / total_sales:.0f}% de tus ventas ocurre en ese horario.",
                "Prueba un happy hour o una once con precio especial para atraer público entre el almuerzo y la cena.",
                "analytics:dashboard", score=55, promo={"tipo": "happy"},
            ))

        # Plato estrella y joya escondida
        if revenue:
            star = max(revenue, key=revenue.get)
            rating = ratings_by_dish.get(star)
            why = f"Es el plato que más ingresos genera ({clp(revenue[star])} en las últimas semanas)"
            if rating and rating["count"] >= 3:
                why += f" y lo valoran con {rating['avg']:.1f}/5".replace(".", ",")
            sections["marketing"].append(_item(
                "⭐", f"Tu plato estrella: {dish_names[star]}", why + ".",
                "Úsalo como imagen principal en redes sociales y destácalo en la portada de la carta.",
                "menus:list", score=50, promo={"tipo": "estrella", "plato": star},
            ))
            median_units = median(units.values())
            gems = [
                (dish_id, row) for dish_id, row in ratings_by_dish.items()
                if row["count"] >= 3 and row["avg"] >= 4.3 and units.get(dish_id, 0) < median_units
            ]
            if gems:
                dish_id, row = max(gems, key=lambda g: g[1]["avg"])
                name = dish_names.get(dish_id) or Dish.objects.get(pk=dish_id).name
                sections["marketing"].append(_item(
                    "💎", f"Joya escondida: {name}",
                    f"Tiene muy buena valoración ({row['avg']:.1f}/5) pero se vende poco ({units.get(dish_id, 0)} unidades).".replace(".", ",", 1),
                    "Recomiéndalo como 'sugerencia del chef' y pide al personal que lo mencione al tomar el pedido.",
                    "menus:list", score=60, promo={"tipo": "joya", "plato": dish_id},
                ))

    # ================= ⭐ Mejoras en la experiencia =================
    worst = sorted(
        (row for row in ratings_by_dish.values() if row["count"] >= 3 and row["avg"] < 3.5),
        key=lambda row: row["avg"],
    )
    if worst:
        row = worst[0]
        name = dish_names.get(row["dish_id"]) or Dish.objects.get(pk=row["dish_id"]).name
        sections["servicio"].append(_item(
            "👎", f"{name} recibe evaluaciones bajas",
            f"Promedio {row['avg']:.1f}/5 en {row['count']} evaluaciones.".replace(".", ",", 1),
            "Revisa la receta, la presentación y el tiempo de salida de este plato.",
            "operations:evaluation_list", score=70,
        ))

    rows = build_dataset(venues, today - timedelta(days=30), today)
    if len(rows) >= 10:
        cut = median(r["ts_minutes"] for r in rows)
        fast = [r["positive_pct"] for r in rows if r["ts_minutes"] <= cut]
        slow = [r["positive_pct"] for r in rows if r["ts_minutes"] > cut]
        if fast and slow:
            fast_avg, slow_avg = sum(fast) / len(fast), sum(slow) / len(slow)
            if fast_avg - slow_avg >= 3:
                synthetic = synthetic or any(r["synthetic"] for r in rows)
                sections["servicio"].append(_item(
                    "⏱️", "Las mesas que esperan más se ven menos contentas",
                    f"Cuando la atención supera los {cut:.0f} minutos, las expresiones positivas bajan "
                    f"de {fast_avg:.0f}% a {slow_avg:.0f}%.",
                    "Agiliza la toma de pedido y la salida de cocina en horas punta: es la mejora de experiencia más clara.",
                    "analytics:correlation", score=68,
                ))

    durations = defaultdict(list)
    for code, started, ended in ServiceSession.objects.filter(
        table__venue__in=venues, status=ServiceSession.Status.CLOSED,
        ended_at__isnull=False, started_at__gte=window_start,
    ).values_list("table__code", "started_at", "ended_at"):
        durations[code].append((ended - started).total_seconds() / 60)
    all_minutes = [m for values in durations.values() for m in values]
    if len(all_minutes) >= 10:
        overall = sum(all_minutes) / len(all_minutes)
        candidates = [(code, sum(v) / len(v)) for code, v in durations.items() if len(v) >= 3]
        if candidates:
            code, average = max(candidates, key=lambda c: c[1])
            if average > overall * 1.10:
                sections["servicio"].append(_item(
                    "🪑", f"La mesa {code} tarda más que el resto",
                    f"{average:.0f} minutos promedio por atención, frente a {overall:.0f} del local.",
                    "Revisa a quién se asigna esa mesa y qué tan lejos está de la cocina.",
                    "operations:session_list", score=50,
                ))

    hourly_counts = Counter(
        timezone.localtime(p).hour for p in paid.filter(paid_at__gte=week_start, paid_at__lt=tomorrow)
        .values_list("paid_at", flat=True)
    )
    if hourly_counts:
        hour, count = hourly_counts.most_common(1)[0]
        share = 100 * count / sum(hourly_counts.values())
        sections["servicio"].append(_item(
            "👥", f"Tu hora más intensa: {hour:02d}:00 a {(hour + 1) % 24:02d}:00",
            f"Concentra el {share:.0f}% de los pagos de la semana.",
            "Refuerza la sala y la cocina en ese horario para no alargar los tiempos de espera.",
            "analytics:dashboard", score=45,
        ))

    for key in sections:
        sections[key].sort(key=lambda item: -item["score"])
        if key != "now":
            sections[key] = sections[key][:per_section]
    sections["synthetic"] = synthetic
    return sections


# Transparencia (K1): cada idea declara su método de cálculo
_build_insights_raw = build_insights


def build_insights(*args, **kwargs):  # noqa: F811
    from .explain import annotate

    result = _build_insights_raw(*args, **kwargs)
    try:
        from operations.services.vision_insights import vision_insights

        venues = args[0] if args else kwargs.get("venues")
        for key, extra in vision_insights(venues).items():
            if isinstance(result.get(key), list):
                result[key] = extra + result[key]
    except Exception:  # noqa: BLE001 — las ideas de visión nunca deben romper el inicio
        import logging

        logging.getLogger("gastroinsight.insights").exception("No se pudieron calcular las ideas de visión")
    return annotate(result)
