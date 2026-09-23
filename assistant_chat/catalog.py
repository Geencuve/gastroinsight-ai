CUSTOMER_SUGGESTIONS = [
    {
        "label": "Ver carta",
        "prompt": "¿Qué platos tienen disponibles?",
        "intent": "customer_menu",
    },
    {
        "label": "Opciones vegetarianas",
        "prompt": "¿Qué opciones vegetarianas tienen?",
        "intent": "customer_dietary_options",
    },
    {
        "label": "Postres y bebidas",
        "prompt": "¿Qué postres y bebidas ofrecen?",
        "intent": "customer_desserts_drinks",
    },
    {
        "label": "Platos recomendados",
        "prompt": "¿Cuáles son los platos mejor evaluados?",
        "intent": "customer_recommended_dishes",
    },
    {
        "label": "Ubicación y contacto",
        "prompt": "¿Dónde queda el local y cómo puedo contactarlo?",
        "intent": "customer_venue_info",
    },
    {
        "label": "Dejar evaluación",
        "prompt": "¿Cómo puedo dejar una evaluación?",
        "intent": "customer_feedback",
    },
]

STAFF_SUGGESTIONS = [
    {
        "label": "Resumen de hoy",
        "prompt": "Dame un resumen operacional de hoy.",
        "intent": "daily_summary",
    },
    {
        "label": "Mesas y sesiones",
        "prompt": "¿Cuántas mesas están abiertas y cuántas sesiones hubo hoy?",
        "intent": "sessions_summary",
    },
    {
        "label": "Atención y evaluaciones",
        "prompt": "¿Cómo estuvo la atención hoy según las evaluaciones?",
        "intent": "service_quality",
    },
    {
        "label": "Platos mejor evaluados",
        "prompt": "¿Cuáles son los platos mejor y peor evaluados esta semana?",
        "intent": "dish_performance",
    },
    {
        "label": "Horario más activo",
        "prompt": "¿Cuál fue el horario de mayor actividad hoy?",
        "intent": "peak_hour",
    },
    {
        "label": "Incidencias abiertas",
        "prompt": "¿Hay incidencias abiertas en el local?",
        "intent": "open_incidents",
    },
    {
        "label": "Estado de cámaras",
        "prompt": "¿Qué cámaras están activas y autorizadas?",
        "intent": "camera_status",
    },
    {
        "label": "Privacidad",
        "prompt": "¿La política de privacidad permite el procesamiento visual?",
        "intent": "privacy_status",
    },
]

PLATFORM_ADMIN_SUGGESTIONS = STAFF_SUGGESTIONS + [
    {
        "label": "Comparar locales",
        "prompt": "Compara el rendimiento de los locales esta semana.",
        "intent": "venue_comparison",
    },
    {
        "label": "Indicadores globales",
        "prompt": "Dame un resumen global de la plataforma hoy.",
        "intent": "platform_summary",
    },
]