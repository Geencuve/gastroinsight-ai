"""Marco legal aplicable y lista de cumplimiento por local.

Las fechas y textos legales están en un solo lugar para actualizarlos fácilmente.
"""
from django.conf import settings

LAW = {
    "current": "Ley N° 19.628",
    "current_name": "Sobre protección de la vida privada (datos personales).",
    "next": "Ley N° 21.719",
    "next_name": "Regula la protección y el tratamiento de los datos personales y crea la Agencia de Protección de Datos Personales. "
                 "Los datos biométricos pasan a ser datos sensibles.",
    "next_date": "1 de diciembre de 2026",
    "next_note": "Fecha programada por la ley. Hay un proyecto del Gobierno para postergarla a 2027: verifica su estado.",
}

# Criterio de la plataforma (no lo fija la ley): plazos acotados según el principio de proporcionalidad
MAX_EVENTS_DAYS = 90
MAX_INCIDENTS_DAYS = 365

PRINCIPLES = [
    ("🎯", "Licitud y finalidad",
     "Solo se analiza video con una política habilitada y una autorización vigente, y únicamente para la finalidad escrita en la política."),
    ("📉", "Proporcionalidad y minimización",
     "Se guardan solo números agregados por mesa (ocupación, IEO, búsqueda de atención). Nunca imágenes, nombres ni identidades."),
    ("🧬", "Datos sensibles (biométricos)",
     "No hay reconocimiento facial ni plantillas biométricas: las expresiones se analizan en el momento, se descartan y no permiten identificar a nadie."),
    ("⏳", "Limitación del plazo",
     f"Cada local define cuánto tiempo conserva los eventos e incidencias (criterio de la plataforma: hasta {MAX_EVENTS_DAYS} y {MAX_INCIDENTS_DAYS} días)."),
    ("🛡️", "Seguridad",
     "Acceso por roles, auditoría de cada cambio y claves de integración guardadas solo como huella SHA-256."),
    ("📢", "Transparencia e información",
     "Aviso visible en el local y la página pública «Privacidad y tus datos» explican qué se mide y para qué."),
    ("🙋", "Derechos de las personas",
     "Acceso, rectificación, supresión, oposición, portabilidad y bloqueo se solicitan por el correo de contacto del local."),
    ("📋", "Responsabilidad proactiva",
     "Cada autorización queda registrada con su responsable y vencimiento, y cada cambio de política queda en la auditoría."),
]


def checklist(venue, policy):
    from cameras.models import Camera

    cameras = Camera.objects.filter(venue=venue, is_active=True).count()
    authorizations = list(policy.authorizations.all()) if policy else []
    valid_auth = any(a.is_valid for a in authorizations)
    enabled = bool(policy and policy.processing_enabled)
    authorized = bool(policy and policy.is_processing_authorized)
    items = []

    def add(ok, label, hint):
        items.append({"ok": bool(ok), "label": label, "hint": hint})

    add(policy and len((policy.purpose or "").strip()) >= 20, "Política con finalidad escrita",
        "Licitud y finalidad: explica para qué se usa el análisis visual.")
    add(valid_auth, "Autorización vigente registrada", "Respaldo formal del uso de las cámaras en el local.")
    add(not enabled or authorized, "Análisis visual solo con autorización",
        "Si está activo, debe existir una autorización vigente.")
    add(cameras == 0 or authorized,
        "Cámaras activas cubiertas" if cameras else "Sin cámaras activas",
        f"{cameras} cámara(s) activa(s): solo se analizan con política y autorización." if cameras else "No hay video que analizar.")
    add(not (policy and policy.store_original_images), "Sin imágenes originales guardadas", "Minimización: solo números agregados.")
    add(policy and policy.retain_aggregated_events_days <= MAX_EVENTS_DAYS and policy.retain_incidents_days <= MAX_INCIDENTS_DAYS,
        "Plazos de conservación acotados",
        f"Eventos hasta {MAX_EVENTS_DAYS} días e incidencias hasta {MAX_INCIDENTS_DAYS} (criterio de la plataforma).")
    add(getattr(settings, "CONTACT_EMAIL", ""), "Correo para ejercer derechos",
        "Configura CONTACT_EMAIL (Centro de gestión → Advertencias de seguridad).")
    done = sum(1 for i in items if i["ok"])
    return {"items": items, "done": done, "total": len(items), "pct": round(100 * done / len(items)),
            "ok": done == len(items), "cameras": cameras, "valid_auth": valid_auth, "enabled": enabled, "authorized": authorized}