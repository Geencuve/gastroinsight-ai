CUSTOMER_SUGGESTIONS = [
    {"label": "Ver carta", "prompt": "¿Qué platos tienen?", "intent": "customer_menu"},
    {"label": "¿Qué me recomiendan?", "prompt": "¿Qué me recomiendan?", "intent": "customer_recommended_dishes"},
    {"label": "Postres y bebidas", "prompt": "¿Qué postres y bebidas tienen?", "intent": "customer_desserts_drinks"},
    {"label": "Opciones vegetarianas", "prompt": "¿Tienen opciones vegetarianas?", "intent": "customer_dietary_options"},
    {"label": "Ubicación", "prompt": "¿Dónde queda el local?", "intent": "customer_venue_info"},
    {"label": "Dejar mi opinión", "prompt": "¿Cómo puedo dejar mi opinión?", "intent": "customer_feedback"},
]

STAFF_SUGGESTIONS = [
    {"label": "📡 Mesas en vivo", "prompt": "¿Cómo están las mesas ahora?", "intent": "live_status"},
    {"label": "🗺️ Estado de la sala", "prompt": "¿Cuál es el estado de las mesas?", "intent": "floor_status"},
    {"label": "📷 Cámaras", "prompt": "¿Cómo están las mediciones por cámara?", "intent": "camera_metrics"},
    {"label": "🛠️ Infraestructura", "prompt": "¿Cómo está la infraestructura?", "intent": "infrastructure"},
    {"label": "📊 Resumen de hoy", "prompt": "Dame el resumen de hoy", "intent": "daily_summary"},
    {"label": "💰 Ventas de la semana", "prompt": "¿Cuánto vendimos esta semana?", "intent": "sales_summary"},
    {"label": "📣 ¿Qué promociono?", "prompt": "¿Qué debería promocionar? Dame ideas de marketing", "intent": "advice"},
    {"label": "🔥 Más vendidos", "prompt": "¿Cuáles son los platos más vendidos?", "intent": "top_dishes"},
    {"label": "💬 Qué dicen los clientes", "prompt": "¿Qué dicen los clientes?", "intent": "customer_comments"},
    {"label": "📅 Día más flojo", "prompt": "¿Cuál es nuestro día más flojo?", "intent": "weekday_sales"},
    {"label": "⏱️ Tiempos de atención", "prompt": "¿Cuánto se demoran las mesas?", "intent": "service_time"},
    {"label": "🧾 Por cobrar", "prompt": "¿Qué hay por cobrar?", "intent": "pending_orders"},
    {"label": "🙂 Expresiones y espera", "prompt": "¿Los clientes están más contentos cuando atendemos rápido?", "intent": "expressions"},
]

PLATFORM_ADMIN_SUGGESTIONS = STAFF_SUGGESTIONS + [
    {"label": "🌐 Resumen global", "prompt": "Dame un resumen global de la plataforma", "intent": "platform_summary"},
    {"label": "🛠️ Incidencias", "prompt": "¿Hay incidencias abiertas?", "intent": "open_incidents"},
]
