"""
Capa de robustez de Sazón: sinónimos, tolerancia a errores de tipeo, «¿quisiste decir…?»,
preguntas de seguimiento por rol, caché breve y respuesta segura ante errores.
Se monta sobre classify_intent y build_staff_response sin cambiar su lógica.
"""
import logging
import re
import time
from difflib import SequenceMatcher

from django.core.cache import cache

logger = logging.getLogger("gastroinsight.sazon")

SYNONYMS = {
    "lucas": "ventas", "plata": "ventas", "facturacion": "ventas", "recaudacion": "ventas",
    "facturamos": "vendimos", "recaudamos": "vendimos", "ganamos": "vendimos", "hicimos": "vendimos",
    "boleta promedio": "ticket promedio", "gasto promedio": "ticket promedio", "consumo promedio": "ticket promedio",
    "platillos": "platos", "platillo": "plato", "garzones": "meseros", "garzon": "mesero",
    "quejas": "comentarios", "reclamos": "comentarios", "opiniones": "comentarios",
    "lo que mas sale": "lo mas vendido", "lo que menos sale": "lo menos vendido",
    "como pagaron": "como pagan", "formas de pago": "medios de pago",
}
CACHEABLE = {"sales_summary", "average_ticket", "weekday_sales", "payment_methods", "top_dishes", "low_dishes",
             "dish_performance", "customer_comments", "advice"}
FOLLOWUPS = {
    "sales_summary": [("🎟️ Ticket promedio", "¿Cuál es el ticket promedio?", "average_ticket"),
                      ("🔥 Más vendidos", "¿Qué es lo más vendido?", "top_dishes"),
                      ("💳 Medios de pago", "¿Cómo pagan los clientes?", "payment_methods")],
    "average_ticket": [("💰 Ventas de hoy", "¿Cuánto vendimos hoy?", "sales_summary"),
                       ("🔥 Más vendidos", "¿Qué es lo más vendido?", "top_dishes")],
    "top_dishes": [("📉 Menos vendidos", "¿Qué es lo menos vendido?", "low_dishes"),
                   ("📣 Qué promociono", "¿Qué debería promocionar?", "advice")],
    "low_dishes": [("🔥 Más vendidos", "¿Qué es lo más vendido?", "top_dishes"),
                   ("📣 Qué promociono", "¿Qué debería promocionar?", "advice")],
    "payment_methods": [("💰 Ventas de hoy", "¿Cuánto vendimos hoy?", "sales_summary"),
                        ("🎟️ Ticket promedio", "¿Cuál es el ticket promedio?", "average_ticket")],
    "live_status": [("🗺️ Estado de la sala", "¿Cuál es el estado de las mesas?", "floor_status"),
                    ("📷 Cámaras", "¿Cómo están las mediciones por cámara?", "camera_metrics")],
    "floor_status": [("🍽️ Listos para servir", "¿Qué platos están listos para servir?", "ready_dishes"),
                     ("🧾 Por cobrar", "¿Qué hay por cobrar?", "pending_orders")],
    "kitchen_queue": [("⭐ Peor evaluados", "¿Cuáles son los platos peor evaluados?", "dish_performance"),
                      ("🍽️ Listos", "¿Qué platos están listos para servir?", "ready_dishes")],
    "bar_queue": [("🍽️ Listos", "¿Qué platos están listos para servir?", "ready_dishes"),
                  ("🔥 Más vendidos", "¿Qué es lo más vendido?", "top_dishes")],
    "cashier_status": [("🧾 Por cobrar", "¿Qué hay por cobrar?", "pending_orders"),
                       ("💳 Medios de pago", "¿Cómo pagan los clientes?", "payment_methods")],
    "camera_metrics": [("🛠️ Infraestructura", "¿Cómo está la infraestructura?", "infrastructure"),
                       ("📡 Mesas en vivo", "¿Cómo están las mesas ahora?", "live_status")],
    "infrastructure": [("📷 Cámaras", "¿Cómo están las mediciones por cámara?", "camera_metrics"),
                       ("📡 Mesas en vivo", "¿Cómo están las mesas ahora?", "live_status")],
    "daily_summary": [("💰 Ventas de hoy", "¿Cuánto vendimos hoy?", "sales_summary"),
                      ("📡 Mesas en vivo", "¿Cómo están las mesas ahora?", "live_status"),
                      ("📣 Qué promociono", "¿Qué debería promocionar?", "advice")],
}

COMMON_WORDS = {
    "que", "cual", "cuales", "como", "cuanto", "cuanta", "cuantos", "cuantas", "donde", "cuando", "quien", "hoy", "ayer",
    "semana", "mes", "dia", "dias", "esta", "este", "estan", "esta", "hay", "tenemos", "vamos", "va", "van", "fue",
    "ventas", "venta", "vendimos", "vendido", "vendidos", "mesa", "mesas", "plato", "platos", "cliente", "clientes",
    "pedido", "pedidos", "cuenta", "caja", "cocina", "barra", "camara", "camaras", "local", "locales", "ahora",
    "mejor", "peor", "mas", "menos", "todo", "todos", "promedio", "ticket", "tiempo", "tiempos", "atencion",
}


def expand(text):
    for word, replacement in sorted(SYNONYMS.items(), key=lambda kv: -len(kv[0])):
        text = re.sub(rf"\b{re.escape(word)}\b", replacement, text)
    return text


def fuzzy_candidates(text, rules):
    """Mejor coincidencia aproximada por intención (solo palabras clave de 5+ letras)."""
    tokens = re.sub(r"[^\w\s]", " ", text).split()  # sin signos: «cosina?» se compara como «cosina»
    best = {}
    for intent, keywords in rules:
        for keyword in keywords:
            if len(keyword) < 5:
                continue
            size = len(keyword.split())
            for start in range(0, max(1, len(tokens) - size + 1)):
                window = " ".join(tokens[start:start + size])
                score = SequenceMatcher(None, window, keyword).ratio()
                if score > best.get(intent, 0):
                    best[intent] = score
    return sorted(best.items(), key=lambda kv: -kv[1])


def edit_distance(a, b):
    """Distancia de edición con intercambio de letras vecinas (Damerau, versión OSA)."""
    if abs(len(a) - len(b)) > 2:
        return 3
    rows = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        rows[i][0] = i
    for j in range(len(b) + 1):
        rows[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            rows[i][j] = min(rows[i - 1][j] + 1, rows[i][j - 1] + 1, rows[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                rows[i][j] = min(rows[i][j], rows[i - 2][j - 2] + 1)
    return rows[len(a)][len(b)]


def correct(text, rules, threshold=0.86, single=True):
    """Corrige errores de tipeo: reemplaza fragmentos muy parecidos (no idénticos) a una frase conocida."""
    tokens = re.sub(r"[^\w\s]", " ", text).split()  # sin signos: «cosina?» se compara como «cosina»
    keywords = sorted({k for _, words in rules for k in words if len(k) >= 5}, key=lambda k: -len(k))
    vocabulary = {word for _, words in rules for k in words for word in k.split()} | COMMON_WORDS
    replacements = []
    for keyword in keywords:
        size = len(keyword.split())
        for start in range(0, max(0, len(tokens) - size + 1)):
            window = " ".join(tokens[start:start + size])
            if window == keyword:
                continue
            if size == 1 and (not single or window in vocabulary):
                continue  # nunca corrige una palabra que ya existe
            score = SequenceMatcher(None, window, keyword).ratio()
            if size == 1 and edit_distance(window, keyword) <= (1 if len(keyword) < 9 else 2):
                score = max(score, threshold)
            if score >= threshold:
                replacements.append((score, start, size, keyword))
    used, chosen = set(), []
    for score, start, size, keyword in sorted(replacements, reverse=True):
        span = set(range(start, start + size))
        if span & used:
            continue
        used |= span
        chosen.append((start, size, keyword))
    for start, size, keyword in sorted(chosen, reverse=True):
        tokens[start:start + size] = keyword.split()
    return " ".join(tokens)


def install(services):
    """Envuelve classify_intent y build_staff_response del módulo de servicios de Sazón."""
    if getattr(services, "_robust_installed", False):
        return
    exact_classify = services.classify_intent
    exact_build = services.build_staff_response

    def classify_intent(message, audience):
        intent = exact_classify(message, audience)
        if audience != "STAFF" or intent == "unsafe_request":
            return intent
        normalized = services.normalize_text(message)
        corrected = correct(expand(normalized), services.STAFF_RULES, single=(intent == "daily_summary"))
        if corrected != normalized:
            alternative = exact_classify(corrected, audience)
            if alternative != "daily_summary":
                return alternative
        if intent != "daily_summary":
            return intent
        candidates = fuzzy_candidates(corrected, services.STAFF_RULES)
        if candidates and candidates[0][1] >= 0.84:
            return candidates[0][0]
        return intent

    def build_staff_response(user, message, *args, **kwargs):
        from authentication.permissions import get_or_create_profile

        from .role_scope import intent_allowed

        started = time.perf_counter()
        normalized = services.normalize_text(message or "")
        if not re.search(r"[a-z0-9]", normalized):
            return ("Escribe tu consulta, por ejemplo «¿Cuánto vendimos hoy?» o «¿Cómo están las mesas ahora?».",
                    "empty", {"elapsed_ms": 0})
        cache_key = f"sazon-answer-{user.pk}-{hash(normalized)}"
        cached = cache.get(cache_key)
        if cached:
            text, intent, meta = cached
            return text, intent, {**meta, "elapsed_ms": round((time.perf_counter() - started) * 1000), "cached": True}
        try:
            text, intent, meta = exact_build(user, message, *args, **kwargs)
        except Exception:  # noqa: BLE001 — Sazón nunca debe mostrar un error técnico
            logger.exception("Sazón no pudo responder: %r", message)
            return ("No pude calcular esa respuesta en este momento. Intenta de nuevo en unos segundos "
                    "o pregunta de otra forma.", "error", {"elapsed_ms": round((time.perf_counter() - started) * 1000)})
        meta = dict(meta or {})
        profile = get_or_create_profile(user)
        meta["followups"] = [{"label": label, "prompt": prompt}
                             for label, prompt, target in FOLLOWUPS.get(intent, FOLLOWUPS["daily_summary"])
                             if target != intent and intent_allowed(profile, target)][:3]
        if exact_classify(message, "STAFF") == "daily_summary" and intent in ("daily_summary", "floor_status",
                                                                             "kitchen_queue", "bar_queue", "cashier_status"):
            candidates = [(c, s) for c, s in fuzzy_candidates(expand(normalized), services.STAFF_RULES)
                          if 0.6 <= s < 0.84 and intent_allowed(profile, c) and c != intent]
            prompts = {target: (label, prompt) for options in FOLLOWUPS.values() for label, prompt, target in options}
            meta["did_you_mean"] = [{"label": prompts[c][0], "prompt": prompts[c][1]} for c, _ in candidates if c in prompts][:3]
        meta["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        if intent in CACHEABLE:
            cache.set(cache_key, (text, intent, meta), 30)
        return text, intent, meta

    services.classify_intent = classify_intent
    services.build_staff_response = build_staff_response
    services._robust_installed = True


def prompts_for(user):
    """Consultas sugeridas para el autocompletado, filtradas por rol."""
    from . import catalog
    from .role_scope import filter_suggestions

    suggestions = getattr(catalog, "STAFF_SUGGESTIONS", [])
    return [{"label": s["label"], "prompt": s["prompt"]} for s in filter_suggestions(user, suggestions)][:40]
