"""
Asistente de GastroInsight AI.

Interpreta consultas en lenguaje natural con reglas transparentes y responde con
datos reales de la plataforma, enlaces directos y consejos de gestión. No envía
información a servicios externos: cada cifra proviene de una consulta verificable.
"""
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from statistics import median
from types import SimpleNamespace

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Sum
from django.db.models.functions import ExtractHour
from django.urls import reverse
from django.utils import timezone

from analytics.services.correlation import build_dataset, correlate
from authentication.permissions import get_or_create_profile
from cameras.models import Camera
from core.services.insights import build_home_summary, build_insights, clp
from menus.models import Dish
from menus.services import sort_dishes
from monitoring.models import Incident
from operations.models import SatisfactionEvaluation, ServiceSession
from privacy.models import PrivacyPolicy
from sales.models import Order, OrderItem
from venues.models import Venue

WEEKDAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

UNSAFE_PHRASES = (
    "ignora las instrucciones", "revela el prompt", "muestra contrasenas",
    "dame credenciales", "borra la base", "elimina datos",
)

STAFF_RULES = [
    ("help", ("que puedes hacer", "ayuda", "como funcionas", "que sabes hacer")),
    ("live_status", ("en vivo", "tiempo real", "como estan las mesas", "mesas ahora", "monitor")),
    ("advice", ("recomienda", "recomendacion", "consejo", "que hago", "que deberia", "como mejoro",
                "como mejorar", "vender mas", "aumentar ventas", "marketing", "promocion", "promocionar",
                "ideas", "oportunidad", "sugerencia", "estrategia")),
    ("pending_orders", ("por cobrar", "sin pagar", "pendiente de pago", "pedidos pendientes", "sin cobrar")),
    ("payment_methods", ("medio de pago", "medios de pago", "efectivo", "tarjeta", "transferencia", "como pagan")),
    ("average_ticket", ("ticket",)),
    ("weekday_sales", ("dia mas flojo", "peor dia", "mejor dia", "dias de la semana", "que dia")),
    ("low_dishes", ("menos vendido", "no se vende", "se vende poco", "menos pedido")),
    ("top_dishes", ("mas vendido", "se vende mas", "mas pedido", "plato estrella", "mas popular")),
    ("dish_performance", ("mejor evaluado", "peor evaluado", "mejor plato", "peor plato",
                          "valoracion de los platos", "rendimiento de platos", "platos mejor", "platos peor")),
    ("customer_comments", ("comentario", "opinion", "que dicen", "resena", "feedback")),
    ("expressions", ("expresion", "emocion", "correlacion", "contentos", "felices", "analisis visual")),
    ("service_time", ("tiempo de atencion", "tiempo de servicio", "demora", "cuanto se demoran",
                      "tarda", "rapidez")),
    ("open_incidents", ("incidencia", "problema tecnico", "falla")),
    ("privacy_status", ("privacidad", "autorizacion", "consentimiento")),
    ("camera_status", ("camara",)),
    ("service_quality", ("satisfaccion", "calidad", "evaluacion", "evaluaciones", "calificacion")),
    ("peak_hour", ("hora mas activa", "hora punta", "mayor actividad", "horario", "a que hora")),
    ("sales_summary", ("venta", "vendi", "vendimos", "facturacion", "ingreso", "recaud", "cuanto se vendio", "caja")),
    ("sessions_summary", ("mesa", "sesion", "comensal", "atendimos")),
    ("platform_summary", ("comparar locales", "resumen global", "plataforma", "todos los locales")),
]

CUSTOMER_RULES = [
    ("customer_feedback", ("evaluar", "opinion", "comentario", "calificar", "reclamo", "felicitar")),
    ("customer_dietary_options", ("vegetar", "vegano", "sin gluten", "alerg", "celiac")),
    ("customer_recommended_dishes", ("recomiend", "mejor plato", "popular", "que me sugieres", "que pido")),
    ("customer_desserts_drinks", ("postre", "bebida", "jugo", "cafe", "trago", "dulce")),
    ("customer_venue_info", ("ubicacion", "direccion", "contacto", "horario", "donde queda", "donde estan")),
    ("customer_menu", ("carta", "menu", "plato", "comida", "precio", "que tienen")),
]


# ======================= Utilidades =======================
def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize_text(text):
    return re.sub(r"\s+", " ", strip_accents((text or "").lower().strip()))


def has(text, *words):
    return any(word in text for word in words)


def _start(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def _range(start_date, end_date):
    return _start(start_date), _start(end_date + timedelta(days=1))


def _link(label, url_name, *args):
    return {"label": label, "url": reverse(url_name, args=args)}


def _fmt(value, decimals=1):
    return f"{value:.{decimals}f}".replace(".", ",")


def get_user_venues(user):
    profile = get_or_create_profile(user)
    if profile.is_platform_admin:
        return Venue.objects.filter(is_active=True)
    return profile.venues.filter(is_active=True)


def get_period_from_message(message):
    text = normalize_text(message)
    today = timezone.localdate()
    match = re.search(r"ultim[oa]s? (\d{1,3}) dias", text)
    if match:
        days = max(1, min(int(match.group(1)), 365))
        return today - timedelta(days=days - 1), today, f"los últimos {days} días"
    if "ayer" in text:
        day = today - timedelta(days=1)
        return day, day, "ayer"
    if has(text, "semana pasada", "semana anterior"):
        end = today - timedelta(days=today.weekday() + 1)
        return end - timedelta(days=6), end, "la semana pasada"
    if "semanal" in text or re.search(r"\bsemana\b", text):
        return today - timedelta(days=today.weekday()), today, "esta semana"
    if has(text, "mes pasado", "mes anterior"):
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end, "el mes pasado"
    if re.search(r"\bmes\b", text) or "mensual" in text:
        return today.replace(day=1), today, "este mes"
    return today, today, "hoy"


def resolve_period(message, default_days):
    """Usa el período pedido; si no se indica ninguno, los últimos `default_days` días."""
    text = normalize_text(message)
    if not has(text, "hoy", "ayer", "semana", "mes", "dias"):
        today = timezone.localdate()
        return today - timedelta(days=default_days - 1), today, f"los últimos {default_days} días"
    return get_period_from_message(message)


def classify_intent(message, audience):
    text = normalize_text(message)
    if has(text, *UNSAFE_PHRASES):
        return "unsafe_request"
    rules = CUSTOMER_RULES if audience == "CUSTOMER" else STAFF_RULES
    for intent, keywords in rules:
        if has(text, *keywords):
            return intent
    return "customer_help" if audience == "CUSTOMER" else "daily_summary"


def find_dish(venues, message):
    """Detecta si la consulta menciona un plato del local (nombre completo o primera palabra)."""
    text = normalize_text(message)
    best, best_score = None, 0
    for dish in Dish.objects.filter(menu__venue__in=venues).select_related("menu"):
        name = normalize_text(re.sub(r"\(.*?\)", "", dish.name)).strip()
        first = name.split(" ")[0] if name else ""
        score = 0
        if name and name in text:
            score = 2 + len(name)
        elif len(first) >= 4 and re.search(rf"\b{re.escape(first)}\b", text):
            score = 1
        if score > best_score:
            best, best_score = dish, score
    return best


def _paid(venues, start_dt, end_dt):
    return Order.objects.filter(
        service_session__table__venue__in=venues, status=Order.Status.PAID,
        paid_at__gte=start_dt, paid_at__lt=end_dt,
    )


# ======================= Funciones de datos (compatibles) =======================
def get_sessions_summary(venues, start_date, end_date):
    sessions = ServiceSession.objects.filter(table__venue__in=venues, started_at__date__range=(start_date, end_date))
    avg_duration = (
        sessions.filter(ended_at__isnull=False)
        .annotate(duration=ExpressionWrapper(F("ended_at") - F("started_at"), output_field=DurationField()))
        .aggregate(value=Avg("duration"))["value"]
    )
    return {
        "total_sessions": sessions.count(),
        "open_sessions": sessions.filter(status=ServiceSession.Status.OPEN).count(),
        "total_guests": sessions.aggregate(total=Sum("guests_count"))["total"] or 0,
        "avg_duration_minutes": round(avg_duration.total_seconds() / 60) if avg_duration else None,
    }


def get_service_quality(venues, start_date, end_date):
    evaluations = SatisfactionEvaluation.objects.filter(
        service_session__table__venue__in=venues, created_at__date__range=(start_date, end_date),
    )
    metrics = evaluations.aggregate(total=Count("id"), average=Avg("rating"))
    return {
        "total_evaluations": metrics["total"] or 0,
        "average_rating": round(metrics["average"], 2) if metrics["average"] else None,
        "negative_count": evaluations.filter(rating__lte=2).count(),
    }


def get_dish_performance(venues, start_date, end_date):
    start_dt, end_dt = _range(start_date, end_date)
    rows = (
        SatisfactionEvaluation.objects.filter(
            service_session__table__venue__in=venues, dish__isnull=False,
            created_at__gte=start_dt, created_at__lt=end_dt,
        )
        .values("dish__name")
        .annotate(average_rating=Avg("rating"), evaluations_count=Count("id"))
        .order_by("-average_rating", "-evaluations_count", "dish__name")
    )
    items = [
        SimpleNamespace(name=r["dish__name"], average_rating=r["average_rating"], evaluations_count=r["evaluations_count"])
        for r in rows
    ]
    return {"best": items[0] if items else None, "worst": items[-1] if items else None,
            "total_dishes": len(items), "items": items}


def get_peak_hour(venues, start_date, end_date):
    return (
        ServiceSession.objects.filter(table__venue__in=venues, started_at__date__range=(start_date, end_date))
        .annotate(hour=ExtractHour("started_at")).values("hour")
        .annotate(total=Count("id")).order_by("-total", "hour").first()
    )


def get_open_incidents(venues):
    return Incident.objects.filter(venue__in=venues, status=Incident.Status.OPEN).order_by("occurred_at")


def get_camera_status(venues):
    return Camera.objects.filter(venue__in=venues).select_related("venue")


def get_privacy_status(venues):
    return PrivacyPolicy.objects.filter(venue__in=venues).select_related("venue")


# ======================= Respuestas del personal =======================
def answer_help():
    return (
        "Puedo responder con los datos de tus locales. Prueba preguntas como:\n"
        "• ¿Cuánto vendimos esta semana?\n"
        "• ¿Qué debería promocionar? / Dame ideas de marketing\n"
        "• ¿Cómo le va al Tiramisú?\n"
        "• ¿Qué dicen los clientes?\n"
        "• ¿Cuál es nuestro día más flojo?\n"
        "• ¿Cuánto se demoran las mesas?\n"
        "• ¿Qué hay por cobrar?\n"
        "También entiendo períodos: hoy, ayer, esta semana, el mes pasado o los últimos 15 días.",
        {"links": [_link("Ir al inicio", "core:home")]},
    )


def answer_sales(venues, message):
    start, end, label = get_period_from_message(message)
    start_dt, end_dt = _range(start, end)
    paid = _paid(venues, start_dt, end_dt)
    agg = paid.aggregate(revenue=Sum("total"), count=Count("id"), avg=Avg("total"))
    links = [_link("Ver reportes", "reports:list"), _link("Abrir dashboard", "analytics:dashboard")]
    if not agg["count"]:
        return f"No hay ventas pagadas registradas para {label}.", {"links": links, "orders": 0}
    span = end_dt - start_dt
    shift = timedelta(days=7) if span <= timedelta(days=7) else span
    compare_end = min(end_dt, timezone.now())
    previous = _paid(venues, start_dt - shift, compare_end - shift).aggregate(total=Sum("total"))["total"]
    compare_label = "al mismo período de la semana anterior" if shift == timedelta(days=7) else "al período anterior"
    text = (f"💰 Ventas de {label}: {clp(agg['revenue'])} en {agg['count']} pedidos pagados "
            f"(ticket promedio {clp(agg['avg'])}).")
    if previous:
        change = 100 * (float(agg["revenue"]) - float(previous)) / float(previous)
        text += f"\nFrente {compare_label} ({clp(previous)}): {change:+.0f}%."
    top = (OrderItem.objects.filter(order__in=paid).values("dish_name")
           .annotate(units=Sum("quantity")).order_by("-units").first())
    if top:
        text += f"\nLo más vendido: {top['dish_name']} ({top['units']} unidades)."
    return text, {"links": links, "orders": agg["count"], "total": float(agg["revenue"])}


def answer_ticket(venues, message):
    start, end, label = resolve_period(message, 7)
    paid = _paid(venues, *_range(start, end))
    agg = paid.aggregate(revenue=Sum("total"), count=Count("id"), avg=Avg("total"))
    links = [_link("Ver reportes", "reports:list")]
    if not agg["count"]:
        return f"No hay pedidos pagados para {label}.", {"links": links}
    guests = ServiceSession.objects.filter(id__in=paid.values("service_session_id")).aggregate(
        total=Sum("guests_count"))["total"] or 0
    text = f"🧾 Ticket promedio de {label}: {clp(agg['avg'])} por pedido ({agg['count']} pedidos)."
    if guests:
        text += f"\nGasto promedio por comensal: {clp(float(agg['revenue']) / guests)}."
    text += "\n💡 Para subirlo: sugiere una entrada para compartir, ofrece postre al retirar los fondos y arma combos con bebida."
    return text, {"links": links}


def answer_top_dishes(venues, message, lowest=False):
    start, end, label = resolve_period(message, 7)
    paid = _paid(venues, *_range(start, end))
    rows = list(OrderItem.objects.filter(order__in=paid).values("dish_id", "dish_name")
                .annotate(units=Sum("quantity"), total=Sum("line_total")).order_by("-units"))
    links = [_link("Ver la carta", "menus:list")]
    if lowest:
        sold = {row["dish_id"]: row["units"] for row in rows}
        available = Dish.objects.filter(menu__venue__in=venues, menu__is_active=True, is_available=True)
        items = sorted(((dish.name, sold.get(dish.id, 0)) for dish in available), key=lambda item: item[1])[:5]
        if not items:
            return "No hay platos disponibles registrados.", {"links": links}
        text = f"🗒️ Platos menos vendidos ({label}):\n" + "\n".join(f"• {name}: {units} unidades" for name, units in items)
        text += "\n💡 Recomiéndalos como sugerencia del chef, prueba una promoción de lanzamiento o reemplázalos por una novedad."
        return text, {"links": links}
    if not rows:
        return f"No hay ventas de platos para {label}.", {"links": links}
    text = f"🔥 Lo más vendido ({label}):\n" + "\n".join(
        f"{i}. {row['dish_name']}: {row['units']} unidades · {clp(row['total'])}" for i, row in enumerate(rows[:5], 1))
    text += "\n💡 Destaca el primero en redes sociales y asegura su stock en hora punta."
    return text, {"links": links}


def answer_dish_performance(venues, message):
    start, end, label = resolve_period(message, 28)
    metrics = get_dish_performance(venues, start, end)
    links = [_link("Ver evaluaciones", "operations:evaluation_list")]
    if not metrics["total_dishes"]:
        return f"No hay evaluaciones de platos para {label}.", {"links": links}
    best, worst = metrics["best"], metrics["worst"]
    text = (f"⭐ Valoración de platos ({label}):\n"
            f"Mejor evaluado: {best.name} con {_fmt(best.average_rating)}/5 ({best.evaluations_count} evaluaciones).\n"
            f"Más bajo: {worst.name} con {_fmt(worst.average_rating)}/5 ({worst.evaluations_count} evaluaciones).")
    if worst.average_rating < 3.5:
        text += f"\n💡 Revisa receta, temperatura y tiempo de salida de {worst.name}."
    return text, {"links": links, "best_dish": best.name, "worst_dish": worst.name}


def answer_comments(venues, message):
    start, end, label = resolve_period(message, 7)
    start_dt, end_dt = _range(start, end)
    evaluations = (SatisfactionEvaluation.objects.filter(
        service_session__table__venue__in=venues, created_at__gte=start_dt, created_at__lt=end_dt,
    ).exclude(comment="").select_related("dish", "service_session__table").order_by("-created_at"))
    links = [_link("Ver evaluaciones", "operations:evaluation_list"), _link("Códigos QR de opinión", "feedback:qr")]
    total = evaluations.count()
    if not total:
        return (f"No hay comentarios de clientes para {label}. "
                "💡 Deja el código QR de opinión en cada mesa para recibir más.", {"links": links})
    low = evaluations.filter(rating__lte=2).count()
    lines = [
        f"• {'★' * e.rating}{'☆' * (5 - e.rating)} \"{e.comment[:120]}\" "
        f"({e.dish.name if e.dish else 'experiencia general'}, mesa {e.service_session.table.code})"
        for e in evaluations[:5]
    ]
    text = f"💬 Comentarios de clientes ({label}): {total} con texto, {low} con nota 1 o 2.\nLos más recientes:\n" + "\n".join(lines)
    if low:
        text += "\n💡 Revisa los comentarios bajos: suelen repetir la misma causa (demora, temperatura o porción)."
    return text, {"links": links}


def answer_expressions(venues, message):
    today = timezone.localdate()
    rows = build_dataset(venues, today - timedelta(days=30), today)
    links = [_link("Panel de correlación", "analytics:correlation")]
    if len(rows) < 3:
        return ("Aún no hay suficientes atenciones con análisis visual asociado para comparar. "
                "Inicia sesiones de análisis en las mesas con cámara.",
                {"links": [_link("Sesiones de análisis", "ai_vision:session_list")]})
    cut = median(row["ts_minutes"] for row in rows)
    fast = [row["positive_pct"] for row in rows if row["ts_minutes"] <= cut]
    slow = [row["positive_pct"] for row in rows if row["ts_minutes"] > cut]
    result = correlate(rows, "ts_minutes", "positive_pct")
    text = f"🙂 Análisis visual agregado ({len(rows)} atenciones, últimos 30 días):"
    if fast and slow:
        text += (f"\nCon atenciones de hasta {cut:.0f} minutos, las expresiones positivas promedian "
                 f"{sum(fast) / len(fast):.0f}%; sobre ese tiempo bajan a {sum(slow) / len(slow):.0f}%.")
    text += f"\nRelación estadística: {result['interpretation']}"
    if any(row["synthetic"] for row in rows):
        text += "\n(Incluye datos sintéticos de demostración.)"
    text += "\nSon estimaciones agregadas: no identifican personas ni miden satisfacción directamente."
    return text, {"links": links}


def answer_service_time(venues, message):
    start, end, label = resolve_period(message, 7)
    start_dt, end_dt = _range(start, end)
    durations = defaultdict(list)
    for code, started, ended in ServiceSession.objects.filter(
        table__venue__in=venues, status=ServiceSession.Status.CLOSED, ended_at__isnull=False,
        started_at__gte=start_dt, started_at__lt=end_dt,
    ).values_list("table__code", "started_at", "ended_at"):
        durations[code].append((ended - started).total_seconds() / 60)
    links = [_link("Atención de mesas", "operations:session_list")]
    values = [m for items in durations.values() for m in items]
    if not values:
        return f"No hay atenciones cerradas para {label}.", {"links": links}
    average = sum(values) / len(values)
    text = f"⏱️ Tiempo promedio de atención ({label}): {average:.0f} minutos en {len(values)} atenciones."
    by_table = {code: sum(v) / len(v) for code, v in durations.items() if len(v) >= 2}
    if len(by_table) >= 2:
        slowest = max(by_table, key=by_table.get)
        fastest = min(by_table, key=by_table.get)
        text += (f"\nMesa más lenta: {slowest} ({by_table[slowest]:.0f} min) · "
                 f"más rápida: {fastest} ({by_table[fastest]:.0f} min).")
        if by_table[slowest] > average * 1.1:
            text += f"\n💡 Revisa la asignación de personal y la distancia a cocina de la mesa {slowest}."
    return text, {"links": links}


def answer_weekday(venues, message):
    today = timezone.localdate()
    start = today - timedelta(days=27)
    totals = Counter()
    for paid_at, total in _paid(venues, *_range(start, today)).values_list("paid_at", "total"):
        totals[timezone.localtime(paid_at).weekday()] += float(total)
    occurrences = Counter((start + timedelta(days=i)).weekday() for i in range(28))
    averages = {wd: totals[wd] / occurrences[wd] for wd in range(7)}
    links = [_link("Ver reportes", "reports:list")]
    if not any(averages.values()):
        return "No hay ventas en las últimas 4 semanas para comparar días.", {"links": links}
    best = max(averages, key=averages.get)
    worst = min(averages, key=averages.get)
    lines = [f"• {WEEKDAY_NAMES[wd]}: {clp(averages[wd])}" for wd in range(7)]
    text = ("📅 Venta promedio por día (últimas 4 semanas):\n" + "\n".join(lines)
            + f"\nMejor día: {WEEKDAY_NAMES[best]} · más flojo: {WEEKDAY_NAMES[worst]}."
            + f"\n💡 Crea una promoción exclusiva para el {WEEKDAY_NAMES[worst].lower()} y anúnciala en redes el día anterior.")
    return text, {"links": links}


def answer_payments(venues, message):
    start, end, label = resolve_period(message, 7)
    rows = (_paid(venues, *_range(start, end)).values("payment_method")
            .annotate(count=Count("id"), total=Sum("total")).order_by("-total"))
    labels = dict(Order.PaymentMethod.choices)
    links = [_link("Ver reportes", "reports:list")]
    if not rows:
        return f"No hay pagos registrados para {label}.", {"links": links}
    grand = sum(float(row["total"]) for row in rows)
    lines = [f"• {labels.get(row['payment_method'], row['payment_method'])}: {clp(row['total'])} "
             f"({row['count']} pedidos · {100 * float(row['total']) / grand:.0f}%)" for row in rows]
    return f"💳 Medios de pago ({label}):\n" + "\n".join(lines), {"links": links}


def answer_pending(venues):
    orders = list(Order.objects.filter(
        service_session__table__venue__in=venues, status__in=[Order.Status.OPEN, Order.Status.CONFIRMED],
    ).select_related("service_session__table").order_by("opened_at"))
    links = [_link("Pedidos y ventas", "sales:order_list")]
    if not orders:
        return "✅ No hay pedidos pendientes de cobro.", {"links": links}
    total = sum(float(order.total) for order in orders)
    lines = [f"• Pedido #{o.id} · mesa {o.service_session.table.code} · {o.get_status_display()} · {clp(o.total)}"
             for o in orders[:8]]
    return f"🧾 {len(orders)} pedido(s) por cobrar, por {clp(total)}:\n" + "\n".join(lines), {"links": links}


def answer_advice(venues, message):
    text_norm = normalize_text(message)
    insights = build_insights(venues)
    if has(text_norm, "marketing", "promo", "redes", "publicidad", "difusion"):
        order = ["marketing", "ventas", "servicio"]
    elif has(text_norm, "servicio", "experiencia", "atencion", "clientes", "satisfaccion"):
        order = ["servicio", "ventas", "marketing"]
    else:
        order = ["ventas", "marketing", "servicio"]
    items = [item for key in order for item in insights[key]][:5]
    if not items:
        return ("Aún no tengo datos suficientes para recomendaciones. Registra atenciones, pedidos y evaluaciones "
                "y vuelve a preguntarme.", {"links": [_link("Ir al inicio", "core:home")]})
    lines = []
    for index, item in enumerate(items, 1):
        line = f"{index}. {item['icon']} {item['title']}\n   → {item['action']}"
        if item["impact"]:
            line += f"\n   Potencial: {item['impact']}"
        lines.append(line)
    text = "Estas son mis recomendaciones según tus datos:\n\n" + "\n".join(lines)
    if insights["now"]:
        text += "\n\n⚠️ Además, para atender ahora: " + "; ".join(item["title"] for item in insights["now"])
    links = [_link("Ver todas las sugerencias", "core:home")]
    seen = set()
    for item in items:
        if item["url"] and item["url"] not in seen and len(links) < 4:
            seen.add(item["url"])
            links.append({"label": item["title"][:38] + ("…" if len(item["title"]) > 38 else ""), "url": item["url"]})
    promo = next((item for item in items if item.get("promo_url")), None)
    if promo:
        links.insert(1, {"label": "🎨 Crear promo", "url": promo["promo_url"]})
    return text, {"links": links}


def answer_dish(venues, dish, message):
    start, end, label = resolve_period(message, 28)
    start_dt, end_dt = _range(start, end)
    paid = _paid(venues, start_dt, end_dt)
    ranking = list(OrderItem.objects.filter(order__in=paid).values("dish_id")
                   .annotate(units=Sum("quantity")).order_by("-units").values_list("dish_id", flat=True))
    sales = OrderItem.objects.filter(order__in=paid, dish=dish).aggregate(units=Sum("quantity"), total=Sum("line_total"))
    units = sales["units"] or 0
    rating = SatisfactionEvaluation.objects.filter(dish=dish, created_at__gte=start_dt, created_at__lt=end_dt).aggregate(
        avg=Avg("rating"), count=Count("id"))
    last = SatisfactionEvaluation.objects.filter(dish=dish).exclude(comment="").order_by("-created_at").first()

    text = f"🍽️ {dish.name} · {dish.category or 'Plato'} · {clp(dish.price)}"
    text += f"\nVentas ({label}): {units} unidades · {clp(sales['total'])}"
    rank = ranking.index(dish.id) + 1 if dish.id in ranking else None
    if rank:
        text += f" · puesto #{rank} de {len(ranking)} platos vendidos"
    if rating["count"]:
        text += f"\nValoración: {_fmt(rating['avg'])}/5 ({rating['count']} evaluaciones)"
    if last:
        text += f"\nÚltimo comentario: \"{last.comment[:120]}\" ({last.rating}/5)"
    if rating["count"] and rating["avg"] < 3.5:
        text += "\n💡 Su valoración es baja: revisa receta, temperatura y tiempo de salida."
    elif rank and rank <= 3:
        partner = "un plato de fondo" if dish.category == "Bebida" else "una bebida"
        text += f"\n💡 Es de tus más vendidos: úsalo en redes o arma un combo con {partner}."
    elif units <= 2:
        text += "\n💡 Se vende poco: pruébalo como sugerencia del chef o evalúa reemplazarlo."
    return text, {"links": [
        _link("Ver en la carta", "menus:detail", dish.menu_id),
        {"label": "🎨 Crear promo", "url": reverse("core:promo_generator") + f"?tipo=estrella&plato={dish.id}"},
    ], "dish": dish.name}


def answer_live(venues):
    from ai_vision.services.live import build_live_state

    state = build_live_state(venues)
    links = [_link("Abrir monitor en vivo", "ai_vision:monitor")]
    if not state["cards"]:
        return "No hay mesas con atención abierta ni cámaras asignadas en este momento.", {"links": links}
    s = state["summary"]
    ieo = f"{s['average_ieo']:.0f}" if s["average_ieo"] is not None else "sin lecturas"
    text = f"📡 Ahora: {s['live_tables']} de {s['tables']} mesas con lectura en vivo · IEO promedio {ieo} · {s['alerts']} alerta(s)."
    for card in state["cards"][:6]:
        value = f"IEO {card['ieo']:.0f}" if card["ieo"] is not None else "sin lectura"
        detail = "; ".join(card["reasons"]) or "sin alertas"
        text += f"\n• Mesa {card['table']}: {value} · {detail}"
    return text, {"links": links}


def answer_daily_summary(venues):
    summary = build_home_summary(venues)
    insights = build_insights(venues)
    text = (f"📊 Resumen de hoy: {clp(summary['sales_today'])} vendidos en {summary['orders_today']} pedidos "
            f"(ticket {clp(summary['average_ticket'])}). {summary['open_tables']} mesas atendiéndose y "
            f"{summary['pending_orders']} pedidos por cobrar.")
    if summary["satisfied_pct"] is not None:
        text += f" Clientes satisfechos (7 días): {summary['satisfied_pct']:.0f}%."
    if insights["now"]:
        text += "\n⚠️ Para atender: " + "; ".join(item["title"] for item in insights["now"])
    ideas = insights["ventas"] + insights["marketing"]
    if ideas:
        text += f"\n💡 Idea del día: {ideas[0]['title']} → {ideas[0]['action']}"
    text += "\n\nPregúntame por ventas, platos, clientes, mesas o pídeme ideas de marketing."
    return text, {"links": [_link("Ver inicio", "core:home"), _link("Dashboard", "analytics:dashboard")]}


def build_staff_response(user, message):
    venues = get_user_venues(user)
    if not venues.exists():
        return "No tienes locales activos asignados para consultar.", "no_venues", {}

    profile = get_or_create_profile(user)
    intent = classify_intent(message, "STAFF")

    if intent == "unsafe_request":
        return ("No puedo revelar credenciales, configuraciones internas ni ejecutar acciones destructivas. "
                "Puedo ayudarte con indicadores y recomendaciones de tus locales.", intent, {})

    if intent not in ("advice", "top_dishes", "low_dishes", "help", "pending_orders", "weekday_sales", "live_status"):
        dish = find_dish(venues, message)
        if dish:
            text, meta = answer_dish(venues, dish, message)
            return text, "dish_detail", meta

    handlers = {
        "help": lambda: answer_help(),
        "live_status": lambda: answer_live(venues),
        "advice": lambda: answer_advice(venues, message),
        "sales_summary": lambda: answer_sales(venues, message),
        "average_ticket": lambda: answer_ticket(venues, message),
        "top_dishes": lambda: answer_top_dishes(venues, message),
        "low_dishes": lambda: answer_top_dishes(venues, message, lowest=True),
        "dish_performance": lambda: answer_dish_performance(venues, message),
        "customer_comments": lambda: answer_comments(venues, message),
        "expressions": lambda: answer_expressions(venues, message),
        "service_time": lambda: answer_service_time(venues, message),
        "weekday_sales": lambda: answer_weekday(venues, message),
        "payment_methods": lambda: answer_payments(venues, message),
        "pending_orders": lambda: answer_pending(venues),
    }
    if intent in handlers:
        text, meta = handlers[intent]()
        return text, intent, meta

    start_date, end_date, period = get_period_from_message(message)

    if intent == "sessions_summary":
        m = get_sessions_summary(venues, start_date, end_date)
        duration = f"{m['avg_duration_minutes']} minutos" if m["avg_duration_minutes"] is not None else "sin atenciones cerradas"
        return (f"🪑 Mesas de {period}: {m['total_sessions']} atenciones, {m['open_sessions']} abiertas, "
                f"{m['total_guests']} comensales y una duración promedio de {duration}.",
                intent, {**m, "links": [_link("Atención de mesas", "operations:session_list")]})

    if intent == "service_quality":
        m = get_service_quality(venues, start_date, end_date)
        links = [_link("Ver evaluaciones", "operations:evaluation_list")]
        if not m["total_evaluations"]:
            return (f"No hay evaluaciones registradas para {period}. 💡 El código QR de opinión ayuda a recibir más.",
                    intent, {**m, "links": links})
        return (f"⭐ Evaluaciones de {period}: {m['total_evaluations']}, con promedio {_fmt(m['average_rating'], 2)}/5 "
                f"y {m['negative_count']} con nota 1 o 2.", intent, {**m, "links": links})

    if intent == "peak_hour":
        peak = get_peak_hour(venues, start_date, end_date)
        if not peak:
            return f"No hay atenciones suficientes para identificar la hora punta de {period}.", intent, {}
        return (f"👥 La hora con más mesas abiertas en {period} fue alrededor de las {peak['hour']:02d}:00 "
                f"({peak['total']} atenciones). 💡 Refuerza sala y cocina en esa franja.",
                intent, {**peak, "links": [_link("Dashboard", "analytics:dashboard")]})

    if intent == "open_incidents":
        incidents = get_open_incidents(venues)
        links = [_link("Ver incidencias", "monitoring:incident_list")]
        if not incidents.exists():
            return "✅ No hay incidencias abiertas en tus locales.", intent, {"open_incidents": 0, "links": links}
        items = "; ".join(f"{i.title} ({i.get_severity_display()})" for i in incidents[:5])
        return f"🛠️ Hay {incidents.count()} incidencia(s) abierta(s): {items}.", intent, {"open_incidents": incidents.count(), "links": links}

    if intent == "camera_status":
        cameras = get_camera_status(venues)
        policies = get_privacy_status(venues)
        authorized = sum(1 for p in policies if p.is_processing_authorized)
        active = cameras.filter(is_active=True).count()
        return (f"📷 Hay {cameras.count()} cámaras registradas, {active} activas, y {authorized} de {policies.count()} "
                f"políticas de privacidad permiten el procesamiento visual. Una cámara activa no queda autorizada "
                f"automáticamente: revisa la política del local.",
                intent, {"camera_count": cameras.count(), "active_camera_count": active,
                         "links": [_link("Sesiones de análisis", "ai_vision:session_list")]})

    if intent == "privacy_status":
        policies = get_privacy_status(venues)
        if not policies.exists():
            return ("No hay políticas de privacidad configuradas: el procesamiento visual debe permanecer bloqueado.",
                    intent, {"policies": 0})
        authorized = sum(1 for p in policies if p.is_processing_authorized)
        return (f"🔒 {policies.count()} política(s) de privacidad; {authorized} permiten el procesamiento visual "
                f"según su configuración y autorización vigente.",
                intent, {"policies": policies.count(), "links": [_link("Privacidad", "privacy:policy_list")]})

    if intent == "platform_summary" and profile.is_platform_admin:
        s = get_sessions_summary(venues, start_date, end_date)
        q = get_service_quality(venues, start_date, end_date)
        total = _paid(venues, *_range(start_date, end_date)).aggregate(total=Sum("total"))["total"]
        return (f"🌐 Resumen global de {period}: {venues.count()} locales activos, {clp(total)} en ventas, "
                f"{s['total_sessions']} atenciones y {q['total_evaluations']} evaluaciones.",
                "platform_summary", {**s, **q})

    text, meta = answer_daily_summary(venues)
    return text, "daily_summary", meta


# ======================= Respuestas al cliente =======================
def get_customer_menu_response(venue):
    dishes = sort_dishes(list(Dish.objects.filter(menu__venue=venue, menu__is_active=True, is_available=True)))
    if not dishes:
        return "No hay platos disponibles registrados en este momento.", {"dish_count": 0}
    groups = defaultdict(list)
    for dish in dishes:
        groups[dish.category or "Otros"].append(f"{dish.name} {clp(dish.price)}")
    lines = [f"{category}: " + ", ".join(items) for category, items in groups.items()]
    return ("🍽️ Nuestra carta:\n" + "\n".join(lines) + "\nMira las fotos en la carta completa.",
            {"dish_count": len(dishes), "links": [_link("Ver carta con fotos", "menus:public", venue.id)]})


def get_customer_recommendations(venue):
    rows = list(
        SatisfactionEvaluation.objects.filter(
            service_session__table__venue=venue, dish__isnull=False, dish__is_available=True,
        ).values("dish__name", "dish__price").annotate(avg=Avg("rating"), count=Count("id"))
        .filter(count__gte=2).order_by("-avg", "-count")[:3]
    )
    links = [_link("Ver carta con fotos", "menus:public", venue.id)]
    if rows:
        items = "\n".join(f"{i}. {r['dish__name']} · ⭐ {_fmt(r['avg'])}/5 · {clp(r['dish__price'])}"
                          for i, r in enumerate(rows, 1))
        return f"⭐ Los platos mejor evaluados por nuestros clientes:\n{items}", {"dish_count": len(rows), "links": links}
    since = timezone.now() - timedelta(days=28)
    popular = list(OrderItem.objects.filter(order__service_session__table__venue=venue, order__status=Order.Status.PAID,
                                            order__paid_at__gte=since)
                   .values("dish_name").annotate(units=Sum("quantity")).order_by("-units")[:3])
    if popular:
        items = ", ".join(row["dish_name"] for row in popular)
        return f"🔥 Lo más pedido por nuestros clientes: {items}.", {"dish_count": len(popular), "links": links}
    return "Aún no tenemos suficientes datos para recomendar platos. ¡Consulta al personal!", {"dish_count": 0, "links": links}


def build_customer_response(venue, message):
    intent = classify_intent(message, "CUSTOMER")
    if intent == "unsafe_request":
        return ("Puedo ayudarte con la carta, los precios, recomendaciones y cómo dejar tu opinión.", intent, {})

    if intent in ("customer_menu", "customer_help", "customer_desserts_drinks"):
        dish = find_dish([venue], message)
        if dish and dish.is_available:
            text = f"🍽️ {dish.name} · {clp(dish.price)}"
            if dish.description:
                text += f"\n{dish.description}"
            rating = SatisfactionEvaluation.objects.filter(dish=dish).aggregate(avg=Avg("rating"), count=Count("id"))
            if rating["count"]:
                text += f"\n⭐ {_fmt(rating['avg'])}/5 según {rating['count']} evaluaciones."
            return text, "customer_dish", {"links": [_link("Ver carta con fotos", "menus:public", venue.id)]}

    if intent == "customer_menu":
        text, meta = get_customer_menu_response(venue)
        return text, intent, meta

    if intent == "customer_dietary_options":
        dishes = Dish.objects.filter(menu__venue=venue, menu__is_active=True, is_available=True,
                                     description__iregex=r"vegetar|vegano|sin gluten|alerg")
        if not dishes.exists():
            return ("No tenemos opciones dietarias etiquetadas en la carta. Consulta al personal por ingredientes, "
                    "alérgenos y contaminación cruzada.", intent, {"dish_count": 0})
        return (f"🥗 Opciones etiquetadas: {', '.join(d.name for d in dishes[:10])}. Confirma siempre ingredientes "
                f"y alérgenos con el personal.", intent, {"dish_count": dishes.count()})

    if intent == "customer_desserts_drinks":
        dishes = Dish.objects.filter(menu__venue=venue, menu__is_active=True, is_available=True,
                                     category__in=("Postre", "Bebida")).order_by("category", "name")
        if not dishes.exists():
            return "No hay postres o bebidas disponibles en este momento.", intent, {"dish_count": 0}
        items = ", ".join(f"{d.name} {clp(d.price)}" for d in dishes[:12])
        return (f"🍰 Postres y bebidas: {items}.", intent,
                {"dish_count": dishes.count(), "links": [_link("Ver carta con fotos", "menus:public", venue.id)]})

    if intent == "customer_recommended_dishes":
        text, meta = get_customer_recommendations(venue)
        return text, intent, meta

    if intent == "customer_venue_info":
        details = [f"📍 {venue.address}"] if venue.address else []
        if venue.description:
            details.append(venue.description)
        return (" ".join(details) or "No hay información adicional registrada.", intent, {"venue_id": venue.id})

    if intent == "customer_feedback":
        return ("⭐ Escanea el código QR de tu mesa para calificar tu experiencia y dejar un comentario. "
                "Es anónimo y nos ayuda a mejorar. No incluyas datos personales.", intent, {})

    return ("Puedo ayudarte con la carta y sus precios, recomendaciones, postres y bebidas, opciones dietarias, "
            "ubicación y cómo dejar tu opinión. También puedes preguntarme por un plato, por ejemplo: "
            "¿cuánto cuesta el pisco sour?", "customer_help",
            {"links": [_link("Ver carta con fotos", "menus:public", venue.id)]})
