"""
Matriz de permisos por rol de GastroInsight AI.

Los permisos se CONFIGURAN aquí (no se entrenan): cada rol declara qué secciones puede abrir.
Lo aplica core.middleware.RoleScopeMiddleware en todas las páginas, y el menú oculta lo que no corresponde.
"""
PLATFORM_ADMIN, VENUE_ADMIN = "platform_admin", "venue_admin"
SUPERVISOR, OPERATOR, VIEWER = "supervisor", "operator", "viewer"
WAITER, KITCHEN, BAR, CASHIER = "waiter", "kitchen", "bar", "cashier"

MANAGERS = {PLATFORM_ADMIN, VENUE_ADMIN}
FULL_OPERATION = MANAGERS | {SUPERVISOR, OPERATOR}

# Secciones comunes a todo el personal
COMMON_PREFIXES = ["/auth/", "/legal/", "/assistant/staff/", "/static/", "/media/", "/primer-uso/"]

# Roles restringidos: rutas que pueden abrir. Los roles que no aparecen aquí no se restringen
# (administradores, operador y visualizador mantienen los permisos de sus propias vistas).
ROLE_PREFIXES = {
    WAITER: ["/operations/sessions/", "/sales/", "/operations/evaluations/", "/opinion/", "/menus/", "/sala/"],
    KITCHEN: ["/cocina/", "/menus/"],
    BAR: ["/barra/", "/menus/"],
    CASHIER: ["/caja/", "/sala/", "/sales/", "/operations/sessions/", "/operations/evaluations/", "/opinion/"],
    SUPERVISOR: ["/operations/", "/sales/", "/opinion/", "/menus/", "/ai/monitor/", "/ai/sessions/", "/cameras/",
                 "/analytics/", "/reports/", "/promociones/", "/monitoring/incidents/",
                 "/sala/", "/cocina/", "/barra/", "/caja/", "/supervisor/"],
}

# Página de inicio de cada rol restringido (se completa en las fases B y C)
ROLE_HOME = {WAITER: "/sala/", KITCHEN: "/cocina/", BAR: "/barra/", CASHIER: "/caja/", SUPERVISOR: "/"}

# Lista que muestra Mi perfil: (etiqueta, roles que la tienen)
PROFILE_CAPABILITIES = [
    ("Ver inicio, dashboard, reportes y correlación", FULL_OPERATION | {VIEWER}),
    ("Operar mesas, pedidos, pagos y evaluaciones", FULL_OPERATION | {WAITER, CASHIER}),
    ("Iniciar análisis visual y el monitor en vivo", FULL_OPERATION),
    ("Pantalla de cocina (comandas)", MANAGERS | {SUPERVISOR, KITCHEN}),
    ("Fila de bebidas (barra)", MANAGERS | {SUPERVISOR, BAR}),
    ("Caja: cobros y termómetro de la mesa", MANAGERS | {SUPERVISOR, OPERATOR, CASHIER}),
    ("Mediciones por cámara", MANAGERS | {SUPERVISOR}),
    ("Gestionar mesas, carta y fotos de platos", MANAGERS),
    ("Editar políticas de privacidad", MANAGERS),
    ("Ver auditoría y administrar la plataforma", {PLATFORM_ADMIN}),
]


def role_key(profile):
    return PLATFORM_ADMIN if profile.is_platform_admin else profile.role


def allowed_prefixes(profile):
    """Rutas permitidas para el rol, o None si el rol no tiene restricción por ruta."""
    if profile.is_platform_admin or profile.user.is_superuser:
        return None
    prefixes = ROLE_PREFIXES.get(profile.role)
    return None if prefixes is None else prefixes + COMMON_PREFIXES


def is_path_allowed(path, prefixes):
    return prefixes is None or path == "/" or any(path.startswith(prefix) for prefix in prefixes)


def home_for(profile):
    return ROLE_HOME.get(profile.role, "/")
