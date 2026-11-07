"""
Qué puede consultar cada rol en Sazón. Es configuración (no entrenamiento):
cada intención declara los roles que la usan y Sazón explica cuando una consulta corresponde a otro rol.
"""
from authentication.roles import BAR, CASHIER, KITCHEN, SUPERVISOR, WAITER, role_key

ROLE_INTENTS = {
    WAITER: {"help", "role_help", "live_status", "floor_status", "ready_dishes", "pending_orders", "service_time",
             "top_dishes", "dish_detail", "customer_comments"},
    KITCHEN: {"help", "role_help", "kitchen_queue", "ready_dishes", "dish_performance", "low_dishes", "top_dishes",
              "dish_detail", "customer_comments"},
    BAR: {"help", "role_help", "bar_queue", "ready_dishes", "dish_performance", "top_dishes", "dish_detail"},
    CASHIER: {"help", "role_help", "cashier_status", "pending_orders", "payment_methods", "average_ticket",
              "sales_summary", "floor_status"},
}
SUPERVISOR_DENIED = {"privacy_status"}
ROLE_DEFAULT = {WAITER: "floor_status", KITCHEN: "kitchen_queue", BAR: "bar_queue", CASHIER: "cashier_status"}
ROLE_HELP = {
    WAITER: "el estado de la sala, los platos listos para servir, lo que falta por cobrar y los tiempos de atención",
    KITCHEN: "las comandas pendientes, los platos listos y la valoración y aceptación de los platos",
    BAR: "las bebidas pendientes, lo que está listo para servir y la valoración de las bebidas",
    CASHIER: "el termómetro de caja, lo que falta por cobrar, los medios de pago y las ventas",
    SUPERVISOR: "la operación en vivo, las mediciones por cámara, la infraestructura y la calidad del servicio",
}
ROLE_CHIPS = {
    WAITER: [("🗺️ Estado de la sala", "¿Cuál es el estado de las mesas?"),
             ("🍽️ Listos para servir", "¿Qué platos están listos para servir?"), ("🧾 Por cobrar", "¿Qué hay por cobrar?")],
    KITCHEN: [("👨‍🍳 Comandas", "¿Cómo va la cocina?"), ("⭐ Platos peor evaluados", "¿Cuáles son los platos peor evaluados?"),
              ("🍽️ Listos", "¿Qué platos están listos para servir?")],
    BAR: [("🍹 Bebidas pendientes", "¿Qué bebidas están pendientes en la barra?"), ("🔥 Más vendidos", "¿Qué es lo más vendido?"),
          ("🍽️ Listos", "¿Qué platos están listos para servir?")],
    CASHIER: [("💵 Termómetro de caja", "¿Cómo está el termómetro de caja?"), ("🧾 Por cobrar", "¿Qué hay por cobrar?"),
              ("💳 Medios de pago", "¿Cómo pagan los clientes?")],
    SUPERVISOR: [("📷 Cámaras", "¿Cómo están las mediciones por cámara?"), ("🗺️ Sala", "¿Cuál es el estado de las mesas?"),
                 ("🛠️ Infraestructura", "¿Cómo está la infraestructura?")],
}
DEFAULT_CHIPS = [("📡 Mesas ahora", "¿Cómo están las mesas ahora?"), ("💰 Ventas de hoy", "¿Cuánto vendimos hoy?"),
                 ("📣 Qué promociono", "¿Qué debería promocionar?")]


def intent_allowed(profile, intent):
    if intent == "how_it_works":
        return True
    key = role_key(profile)
    if key in ROLE_INTENTS:
        return intent in ROLE_INTENTS[key]
    if key == SUPERVISOR:
        return intent not in SUPERVISOR_DENIED
    return True


def resolve_intent_for_role(profile, intent):
    """Devuelve (intención, mensaje_de_rechazo). El mensaje es None si el rol puede consultarla."""
    key = role_key(profile)
    if intent == "help" and key in ROLE_HELP:
        return "role_help", None
    if intent_allowed(profile, intent):
        return intent, None
    if intent == "daily_summary" and key in ROLE_DEFAULT:
        return ROLE_DEFAULT[key], None
    role = profile.get_role_display().lower()
    return intent, (f"Esa consulta corresponde a otro rol. Como {role} puedo ayudarte con "
                    f"{ROLE_HELP.get(key, 'las funciones de tu rol')}.")


def filter_suggestions(user, suggestions):
    from authentication.permissions import get_or_create_profile

    profile = get_or_create_profile(user)
    allowed = [s for s in suggestions if intent_allowed(profile, s.get("intent", "help"))]
    extra = [{"label": label, "prompt": prompt, "intent": "role"} for label, prompt in ROLE_CHIPS.get(role_key(profile), [])]
    return extra + [s for s in allowed if s["prompt"] not in {e["prompt"] for e in extra}]


def chips_for(profile):
    return [{"label": label, "prompt": prompt} for label, prompt in ROLE_CHIPS.get(role_key(profile), DEFAULT_CHIPS)]
