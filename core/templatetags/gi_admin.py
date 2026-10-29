from django import template
from django.apps import apps
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()

ICON_PATHS = {
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "store": '<path d="M3 9l1.5-5h15L21 9"/><path d="M4 9v11h16V9"/><path d="M9 20v-6h6v6"/><path d="M3 9h18"/>',
    "utensils": '<path d="M3 2v7a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/><path d="M21 15V2a5 5 0 0 0-5 5v6a2 2 0 0 0 2 2h3v7"/>',
    "receipt": '<path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 3 2V2l-3 2-3-2-3 2-3-2-3 2z"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    "camera": '<path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
    "eye": '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
    "lock": '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "back": '<path d="M19 12H5M11 18l-6-6 6-6"/>',
}

SECTIONS = [
    {"icon": "utensils", "title": "Operación del local", "subtitle": "Mesas, atención, pedidos y evaluaciones", "wide": True,
     "models": [("operations", "restauranttable"), ("operations", "servicesession"), ("sales", "order"),
                ("sales", "orderitem"), ("operations", "satisfactionevaluation")]},
    {"icon": "book", "title": "Locales y carta", "subtitle": "Locales, menús y platos", "wide": False,
     "models": [("venues", "venue"), ("menus", "menu"), ("menus", "dish")]},
    {"icon": "eye", "title": "Visión IA", "subtitle": "Cámaras, sesiones y eventos agregados", "wide": False,
     "models": [("cameras", "camera"), ("ai_vision", "analysissession"), ("ai_vision", "detectionevent")]},
    {"icon": "lock", "title": "Usuarios, privacidad y control", "subtitle": "Accesos, roles, privacidad, incidencias y auditoría", "wide": True,
     "models": [("auth", "user"), ("auth", "group"), ("authentication", "profile"), ("privacy", "privacypolicy"),
                ("privacy", "processingauthorization"), ("monitoring", "incident"), ("monitoring", "auditlog")]},
]


@register.simple_tag
def gi_icon(name, size=18):
    path = ICON_PATHS.get(name, ICON_PATHS["grid"])
    return mark_safe(
        f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="currentColor" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>'
    )


@register.simple_tag
def gi_app_icon(app_label):
    return gi_icon("grid")


def _url(name):
    try:
        return reverse(name)
    except NoReverseMatch:
        return "#"


def _tile(key, model_info):
    try:
        count = apps.get_model(*key).objects.count()
    except LookupError:
        count = None
    return {"name": model_info["name"], "count": count,
            "admin_url": model_info.get("admin_url"), "add_url": model_info.get("add_url")}


@register.simple_tag
def gi_admin_sections(app_list):
    available = {
        (app["app_label"], model["object_name"].lower()): model
        for app in app_list for model in app["models"]
    }
    used, sections = set(), []
    for spec in SECTIONS:
        tiles = []
        for key in spec["models"]:
            if key in available:
                used.add(key)
                tiles.append(_tile(key, available[key]))
        if tiles:
            sections.append({**spec, "tiles": tiles})
    rest = [_tile(key, model) for key, model in available.items() if key not in used]
    if rest:
        sections.append({"icon": "grid", "title": "Otros módulos", "subtitle": "Datos complementarios", "wide": True, "tiles": rest})
    return sections


@register.simple_tag
def gi_admin_stats():
    from django.contrib.auth.models import User

    from cameras.models import Camera
    from monitoring.models import Incident
    from operations.models import ServiceSession
    from sales.models import Order
    from venues.models import Venue

    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return [
        {"icon": "users", "label": "Usuarios activos", "value": User.objects.filter(is_active=True).count(),
         "url": _url("admin:auth_user_changelist")},
        {"icon": "store", "label": "Locales activos", "value": Venue.objects.filter(is_active=True).count(),
         "url": _url("admin:venues_venue_changelist")},
        {"icon": "utensils", "label": "Mesas abiertas", "value": ServiceSession.objects.filter(status="open").count(),
         "url": _url("admin:operations_servicesession_changelist")},
        {"icon": "receipt", "label": "Pedidos de hoy", "value": Order.objects.filter(opened_at__gte=start).count(),
         "url": _url("admin:sales_order_changelist")},
        {"icon": "camera", "label": "Cámaras activas", "value": Camera.objects.filter(is_active=True).count(),
         "url": _url("admin:cameras_camera_changelist")},
        {"icon": "shield", "label": "Incidencias abiertas", "value": Incident.objects.filter(status=Incident.Status.OPEN).count(),
         "url": _url("admin:monitoring_incident_changelist")},
    ]
