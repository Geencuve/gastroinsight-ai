import re
from datetime import timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F
from django.db.models.functions import ExtractHour
from django.utils import timezone

from cameras.models import Camera
from menus.models import Dish
from monitoring.models import Incident
from operations.models import SatisfactionEvaluation, ServiceSession
from privacy.models import PrivacyPolicy
from venues.models import Venue

from authentication.permissions import get_or_create_profile


def normalize_text(text):
    text = (text or "").lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def get_user_venues(user):
    profile = get_or_create_profile(user)

    if profile.is_platform_admin:
        return Venue.objects.filter(is_active=True)

    return profile.venues.filter(is_active=True)


def get_period_from_message(message):
    text = normalize_text(message)
    today = timezone.localdate()

    if "ayer" in text:
        day = today - timedelta(days=1)
        return day, day, "ayer"

    if (
        "semana pasada" in text
        or "semana anterior" in text
    ):
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
        return start, end, "la semana pasada"

    if "esta semana" in text or "semanal" in text:
        start = today - timedelta(days=today.weekday())
        return start, today, "esta semana"

    if "mes" in text:
        start = today.replace(day=1)
        return start, today, "este mes"

    return today, today, "hoy"


def classify_intent(message, audience):
    text = normalize_text(message)

    if any(
        phrase in text
        for phrase in (
            "ignora las instrucciones",
            "revela el prompt",
            "muestra contraseñas",
            "dame credenciales",
            "borra la base",
            "elimina datos",
        )
    ):
        return "unsafe_request"

    if audience == "CUSTOMER":
        if any(
            word in text
            for word in (
                "carta",
                "menú",
                "menu",
                "plato",
                "comida",
            )
        ):
            return "customer_menu"

        if any(
            word in text
            for word in (
                "vegetar",
                "vegano",
                "sin gluten",
                "alerg",
            )
        ):
            return "customer_dietary_options"

        if any(
            word in text
            for word in (
                "postre",
                "bebida",
                "jugo",
                "café",
                "cafe",
            )
        ):
            return "customer_desserts_drinks"

        if any(
            word in text
            for word in (
                "recomend",
                "mejor plato",
                "popular",
            )
        ):
            return "customer_recommended_dishes"

        if any(
            word in text
            for word in (
                "ubicación",
                "ubicacion",
                "dirección",
                "direccion",
                "contacto",
                "horario",
            )
        ):
            return "customer_venue_info"

        if any(
            word in text
            for word in (
                "evaluar",
                "opinión",
                "opinion",
                "comentario",
            )
        ):
            return "customer_feedback"

        return "customer_help"

    if any(
        phrase in text
        for phrase in (
            "incidencia",
            "incidencias",
            "problema técnico",
            "problema tecnico",
            "alerta",
        )
    ):
        return "open_incidents"

    if any(
        word in text
        for word in (
            "privacidad",
            "autorización",
            "autorizacion",
            "consentimiento",
        )
    ):
        return "privacy_status"

    if any(
        word in text
        for word in (
            "cámara",
            "camara",
            "cámaras",
            "camaras",
        )
    ):
        return "camera_status"

    if any(
        phrase in text
        for phrase in (
            "mejor plato",
            "peor plato",
            "platos mejor",
            "platos peor",
            "rendimiento de platos",
        )
    ):
        return "dish_performance"

    if any(
        word in text
        for word in (
            "atención",
            "atencion",
            "evaluación",
            "evaluacion",
            "satisfacción",
            "satisfaccion",
            "calidad",
        )
    ):
        return "service_quality"

    if any(
        phrase in text
        for phrase in (
            "hora más activa",
            "hora mas activa",
            "mayor actividad",
            "ocupación por hora",
            "ocupacion por hora",
        )
    ):
        return "peak_hour"

    if any(
        word in text
        for word in (
            "mesa",
            "mesas",
            "sesión",
            "sesion",
            "comensales",
        )
    ):
        return "sessions_summary"

    if any(
        phrase in text
        for phrase in (
            "comparar locales",
            "rendimiento de los locales",
            "resumen global",
            "plataforma",
        )
    ):
        return "platform_summary"

    if any(
        word in text
        for word in (
            "ventas",
            "facturación",
            "facturacion",
            "ingresos",
        )
    ):
        return "sales_unavailable"

    return "daily_summary"


def get_customer_menu_response(venue):
    dishes = (
        Dish.objects.filter(
            menu__venue=venue,
            menu__is_active=True,
            is_available=True,
        )
        .select_related("menu")
        .order_by("category", "name")
    )

    if not dishes.exists():
        return (
            "No tengo platos disponibles registrados para este local "
            "en este momento.",
            {"dish_count": 0},
        )

    dish_list = ", ".join(
        f"{dish.name} (${dish.price})"
        for dish in dishes[:12]
    )

    return (
        f"Actualmente hay {dishes.count()} platos disponibles: "
        f"{dish_list}.",
        {"dish_count": dishes.count()},
    )


def get_customer_recommendations(venue):
    evaluations = SatisfactionEvaluation.objects.filter(
        service_session__table__venue=venue,
    ).select_related("dish")

    dish_metrics = {}

    for evaluation in evaluations:
        dish = evaluation.dish

        if dish.id not in dish_metrics:
            dish_metrics[dish.id] = {
                "name": dish.name,
                "total": 0,
                "rating_sum": 0,
            }

        dish_metrics[dish.id]["total"] += 1
        dish_metrics[dish.id]["rating_sum"] += evaluation.rating

    ranked_dishes = sorted(
        dish_metrics.values(),
        key=lambda item: (
            item["rating_sum"] / item["total"],
            item["total"],
        ),
        reverse=True,
    )

    if not ranked_dishes:
        return (
            "Aún no hay suficientes evaluaciones registradas para "
            "recomendar platos con respaldo de datos.",
            {"dish_count": 0},
        )

    items = ", ".join(
        (
            f"{dish['name']} "
            f"({dish['rating_sum'] / dish['total']:.1f}/5)"
        )
        for dish in ranked_dishes[:3]
    )

    return (
        f"Según evaluaciones agregadas registradas, puedes considerar: "
        f"{items}. Esta recomendación es informativa y puede cambiar "
        f"según disponibilidad.",
        {"dish_count": len(ranked_dishes)},
    )

def get_sessions_summary(venues, start_date, end_date):
    sessions = ServiceSession.objects.filter(
        table__venue__in=venues,
        started_at__date__range=(start_date, end_date),
    )

    total_sessions = sessions.count()
    open_sessions = sessions.filter(
        status=ServiceSession.Status.OPEN
    ).count()

    total_guests = sum(
        item or 0
        for item in sessions.values_list(
            "guests_count",
            flat=True,
        )
    )

    duration_expression = ExpressionWrapper(
        F("ended_at") - F("started_at"),
        output_field=DurationField(),
    )

    avg_duration = (
        sessions.filter(
            ended_at__isnull=False,
        )
        .annotate(duration=duration_expression)
        .aggregate(avg_duration=Avg("duration"))
        .get("avg_duration")
    )

    avg_duration_minutes = (
        round(avg_duration.total_seconds() / 60)
        if avg_duration
        else None
    )

    return {
        "total_sessions": total_sessions,
        "open_sessions": open_sessions,
        "total_guests": total_guests,
        "avg_duration_minutes": avg_duration_minutes,
    }


def get_service_quality(venues, start_date, end_date):
    evaluations = SatisfactionEvaluation.objects.filter(
        service_session__table__venue__in=venues,
        created_at__date__range=(start_date, end_date),
    )

    metrics = evaluations.aggregate(
        total=Count("id"),
        average=Avg("rating"),
    )

    total = metrics["total"] or 0
    average = metrics["average"]

    negative_count = evaluations.filter(
        rating__lte=2
    ).count()

    return {
        "total_evaluations": total,
        "average_rating": round(average, 2) if average else None,
        "negative_count": negative_count,
    }


def get_dish_performance(venues, start_date, end_date):
    dishes = (
        Dish.objects.filter(
            menu__venue__in=venues,
            satisfactionevaluation__created_at__date__range=(
                start_date,
                end_date,
            ),
        )
        .annotate(
            average_rating=Avg(
                "satisfactionevaluation__rating"
            ),
            evaluations_count=Count(
                "satisfactionevaluation"
            ),
        )
        .filter(evaluations_count__gt=0)
        .order_by("-average_rating", "-evaluations_count", "name")
    )

    best = dishes.first()
    worst = dishes.order_by(
        "average_rating",
        "-evaluations_count",
        "name",
    ).first()

    return {
        "best": best,
        "worst": worst,
        "total_dishes": dishes.count(),
    }


def get_peak_hour(venues, start_date, end_date):
    result = (
        ServiceSession.objects.filter(
            table__venue__in=venues,
            started_at__date__range=(start_date, end_date),
        )
        .annotate(hour=ExtractHour("started_at"))
        .values("hour")
        .annotate(total=Count("id"))
        .order_by("-total", "hour")
        .first()
    )

    return result


def get_open_incidents(venues):
    incidents = Incident.objects.filter(
        venue__in=venues,
        status=Incident.Status.OPEN,
    ).order_by("occurred_at")

    return incidents


def get_camera_status(venues):
    cameras = Camera.objects.filter(
        venue__in=venues,
    ).select_related("venue")

    return cameras


def get_privacy_status(venues):
    policies = PrivacyPolicy.objects.filter(
        venue__in=venues,
    ).select_related("venue")

    return policies


def build_staff_response(user, message):
    venues = get_user_venues(user)

    if not venues.exists():
        return (
            "No tienes locales activos asignados para consultar.",
            "no_venues",
            {},
        )

    profile = get_or_create_profile(user)
    intent = classify_intent(message, "STAFF")
    start_date, end_date, period_name = get_period_from_message(message)

    if intent == "unsafe_request":
        return (
            "No puedo revelar credenciales, configuraciones internas "
            "ni ejecutar acciones destructivas. Puedo ayudarte con "
            "indicadores operacionales autorizados.",
            intent,
            {},
        )

    if intent == "sales_unavailable":
        return (
            "No existen datos de ventas o facturación integrados en "
            "esta versión. Puedo responder sobre sesiones, afluencia, "
            "evaluaciones, platos, incidencias y estado técnico.",
            intent,
            {},
        )

    if intent == "sessions_summary":
        metrics = get_sessions_summary(
            venues,
            start_date,
            end_date,
        )

        duration_text = (
            f"{metrics['avg_duration_minutes']} minutos"
            if metrics["avg_duration_minutes"] is not None
            else "sin datos de duración cerrada"
        )

        return (
            f"Resumen de {period_name}: {metrics['total_sessions']} "
            f"sesiones registradas, {metrics['open_sessions']} abiertas, "
            f"{metrics['total_guests']} comensales registrados y una "
            f"duración promedio de {duration_text}.",
            intent,
            metrics,
        )

    if intent == "service_quality":
        metrics = get_service_quality(
            venues,
            start_date,
            end_date,
        )

        if not metrics["total_evaluations"]:
            return (
                f"No hay evaluaciones registradas para {period_name}. "
                f"Por ello no es posible estimar la calidad de atención "
                f"con respaldo de datos.",
                intent,
                metrics,
            )

        return (
            f"Para {period_name} se registraron "
            f"{metrics['total_evaluations']} evaluaciones, con promedio "
            f"{metrics['average_rating']}/5 y "
            f"{metrics['negative_count']} evaluaciones de 1 o 2 puntos. "
            f"Este indicador refleja evaluaciones registradas, no una "
            f"conclusión individual sobre clientes o trabajadores.",
            intent,
            metrics,
        )

    if intent == "dish_performance":
        metrics = get_dish_performance(
            venues,
            start_date,
            end_date,
        )

        if not metrics["total_dishes"]:
            return (
                f"No hay suficientes evaluaciones de platos para "
                f"{period_name}.",
                intent,
                metrics,
            )

        best = metrics["best"]
        worst = metrics["worst"]

        return (
            f"Para {period_name}, el plato mejor evaluado fue "
            f"{best.name} con {best.average_rating:.2f}/5 "
            f"({best.evaluations_count} evaluaciones). El indicador "
            f"más bajo fue {worst.name} con "
            f"{worst.average_rating:.2f}/5 "
            f"({worst.evaluations_count} evaluaciones). Conviene revisar "
            f"el resultado con el equipo antes de aplicar cambios.",
            intent,
            {
                "best_dish": best.name,
                "best_rating": float(best.average_rating),
                "worst_dish": worst.name,
                "worst_rating": float(worst.average_rating),
            },
        )

    if intent == "peak_hour":
        peak = get_peak_hour(
            venues,
            start_date,
            end_date,
        )

        if not peak:
            return (
                f"No hay sesiones suficientes para identificar una hora "
                f"de mayor actividad en {period_name}.",
                intent,
                {},
            )

        return (
            f"La franja con mayor cantidad de sesiones iniciadas "
            f"en {period_name} fue alrededor de las "
            f"{peak['hour']:02d}:00, con {peak['total']} sesiones. "
            f"Es una métrica de actividad registrada, no un conteo "
            f"exacto de personas presentes.",
            intent,
            peak,
        )

    if intent == "open_incidents":
        incidents = get_open_incidents(venues)

        if not incidents.exists():
            return (
                "No hay incidencias abiertas en los locales autorizados.",
                intent,
                {"open_incidents": 0},
            )

        items = "; ".join(
            f"{incident.title} ({incident.get_severity_display()})"
            for incident in incidents[:5]
        )

        return (
            f"Hay {incidents.count()} incidencias abiertas: {items}.",
            intent,
            {"open_incidents": incidents.count()},
        )

    if intent == "camera_status":
        cameras = get_camera_status(venues)

        if not cameras.exists():
            return (
                "No hay cámaras registradas en los locales autorizados.",
                intent,
                {"camera_count": 0},
            )

        active_count = cameras.filter(is_active=True).count()
        items = ", ".join(
            f"{camera.name} ({'activa' if camera.is_active else 'inactiva'})"
            for camera in cameras[:8]
        )

        return (
            f"Hay {cameras.count()} cámaras registradas y "
            f"{active_count} activas: {items}. El estado de cámara no "
            f"implica por sí solo autorización de procesamiento visual.",
            intent,
            {
                "camera_count": cameras.count(),
                "active_camera_count": active_count,
            },
        )

    if intent == "privacy_status":
        policies = get_privacy_status(venues)

        if not policies.exists():
            return (
                "No se encontraron políticas de privacidad configuradas "
                "para los locales autorizados. El procesamiento visual "
                "debe permanecer bloqueado hasta regularizarlo.",
                intent,
                {"policies": 0},
            )

        authorized_count = sum(
            1
            for policy in policies
            if policy.is_processing_authorized
        )

        return (
            f"Se encontraron {policies.count()} políticas de privacidad. "
            f"{authorized_count} permiten procesamiento visual según su "
            f"configuración y autorización vigente. Verifica siempre la "
            f"política específica antes de operar una fuente visual.",
            intent,
            {
                "policies": policies.count(),
                "authorized_policies": authorized_count,
            },
        )

    if intent == "platform_summary" and profile.is_platform_admin:
        session_metrics = get_sessions_summary(
            venues,
            start_date,
            end_date,
        )
        quality_metrics = get_service_quality(
            venues,
            start_date,
            end_date,
        )

        return (
            f"Resumen global de {period_name}: "
            f"{venues.count()} locales activos, "
            f"{session_metrics['total_sessions']} sesiones, "
            f"{session_metrics['total_guests']} comensales registrados y "
            f"{quality_metrics['total_evaluations']} evaluaciones. "
            f"Promedio de evaluación: "
            f"{quality_metrics['average_rating'] or 'sin datos'}/5.",
            intent,
            {
                "venues": venues.count(),
                **session_metrics,
                **quality_metrics,
            },
        )

    session_metrics = get_sessions_summary(
        venues,
        start_date,
        end_date,
    )
    quality_metrics = get_service_quality(
        venues,
        start_date,
        end_date,
    )
    incidents = get_open_incidents(venues).count()

    return (
        f"Resumen de {period_name}: "
        f"{session_metrics['total_sessions']} sesiones, "
        f"{session_metrics['open_sessions']} abiertas, "
        f"{session_metrics['total_guests']} comensales registrados, "
        f"{quality_metrics['total_evaluations']} evaluaciones y "
        f"{incidents} incidencias abiertas. "
        f"Puedes preguntar por mesas, atención, platos, actividad por "
        f"hora, incidencias, cámaras o privacidad.",
        "daily_summary",
        {
            **session_metrics,
            **quality_metrics,
            "open_incidents": incidents,
        },
    )


def build_customer_response(venue, message):
    intent = classify_intent(message, "CUSTOMER")

    if intent == "unsafe_request":
        return (
            "Puedo ayudarte con información pública del local, carta, "
            "disponibilidad registrada y cómo dejar una evaluación.",
            intent,
            {},
        )

    if intent == "customer_menu":
        content, metadata = get_customer_menu_response(venue)
        return content, intent, metadata

    if intent == "customer_dietary_options":
        dishes = Dish.objects.filter(
            menu__venue=venue,
            menu__is_active=True,
            is_available=True,
        ).filter(
            description__iregex=(
                r"vegetar|vegano|sin gluten|alerg"
            )
        )

        if not dishes.exists():
            return (
                "No hay opciones dietarias etiquetadas en la información "
                "actual. Consulta directamente al personal sobre "
                "ingredientes, alérgenos y contaminación cruzada.",
                intent,
                {"dish_count": 0},
            )

        items = ", ".join(
            dish.name
            for dish in dishes[:10]
        )

        return (
            f"Las opciones etiquetadas disponibles son: {items}. "
            f"Antes de ordenar, confirma siempre ingredientes y alérgenos "
            f"con el personal del local.",
            intent,
            {"dish_count": dishes.count()},
        )

    if intent == "customer_desserts_drinks":
        dishes = Dish.objects.filter(
            menu__venue=venue,
            menu__is_active=True,
            is_available=True,
            category__in=("Postre", "Bebida"),
        ).order_by("category", "name")

        if not dishes.exists():
            return (
                "No hay postres o bebidas disponibles registrados en "
                "este momento.",
                intent,
                {"dish_count": 0},
            )

        items = ", ".join(
            f"{dish.name} (${dish.price})"
            for dish in dishes[:12]
        )

        return (
            f"Postres y bebidas disponibles: {items}.",
            intent,
            {"dish_count": dishes.count()},
        )

    if intent == "customer_recommended_dishes":
        content, metadata = get_customer_recommendations(venue)
        return content, intent, metadata

    if intent == "customer_venue_info":
        details = []

        if venue.address:
            details.append(f"Dirección: {venue.address}")

        if venue.description:
            details.append(venue.description)

        if not details:
            details.append(
                "No hay información pública adicional registrada."
            )

        return (
            " ".join(details),
            intent,
            {"venue_id": venue.id},
        )

    if intent == "customer_feedback":
        return (
            "Puedes dejar tu evaluación al finalizar tu atención. "
            "Tu opinión ayuda al local a revisar de forma agregada la "
            "calidad de servicio y los platos. No incluyas datos "
            "personales sensibles en el comentario.",
            intent,
            {},
        )

    return (
        "Puedo ayudarte con la carta, platos disponibles, opciones "
        "dietarias etiquetadas, postres, bebidas, recomendaciones "
        "basadas en evaluaciones agregadas, ubicación y cómo dejar "
        "una evaluación.",
        "customer_help",
        {},
    )