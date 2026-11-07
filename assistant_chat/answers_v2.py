"""Respuestas de Sazón para las funciones por rol: sala, cocina, barra, caja, cámaras e infraestructura."""
from datetime import timedelta

from django.db.models import Avg, Count
from django.urls import reverse
from django.utils import timezone


def _link(label, name):
    return {"label": label, "url": reverse(name)}


def _clp(value):
    return "$" + f"{int(value or 0):,}".replace(",", ".")


def _dec(value, digits=1):
    return f"{value:.{digits}f}".replace(".", ",") if value is not None else "—"


def answer_station(venues, station):
    from sales.services.kitchen import STATIONS, acceptance, queue

    config = STATIONS[station]
    data = queue(venues, station)
    counts = {column["status"]: len(column["cards"]) for column in data["columns"]}
    waiting = [card for column in data["columns"] if column["status"] != "ready" for card in column["cards"]]
    oldest = max(waiting, key=lambda card: card["minutes"], default=None)
    text = (f"{config['icon']} {config['title']} ahora: {counts.get('pending', 0)} pendientes, "
            f"{counts.get('preparing', 0)} en preparación y {counts.get('ready', 0)} listos para servir.")
    if oldest:
        text += (f"\nLa comanda más antigua es de la mesa {oldest['table'].code} y lleva {oldest['minutes']} min"
                 + (" (atrasada)." if oldest["level"] == "late" else "."))
    rows = acceptance(venues, station)
    rated = sorted((r for r in rows if r["csat"] is not None), key=lambda r: r["csat"])
    if rated:
        text += f"\nMenor valoración en 7 días: {rated[0]['name']} ({_dec(rated[0]['csat'])} ★)."
    dropping = sorted((r for r in rows if r["ibe_delta"] is not None and r["ibe_delta"] < 0), key=lambda r: r["ibe_delta"])
    if dropping:
        text += (f"\n{dropping[0]['name']}: el balance de expresiones de las mesas baja tras recibirlo "
                 f"({_dec(dropping[0]['ibe_delta'], 2)}). Revisa presentación, temperatura o tiempos.")
    top = max((r["units"] for r in rows), default=0) or 1
    return text, {
        "links": [_link(f"Abrir {config['title'].lower()}", "kitchen:home" if station == "cocina" else "bar:home")],
        "metrics": [{"label": "Pendientes", "value": str(counts.get("pending", 0))},
                    {"label": "En preparación", "value": str(counts.get("preparing", 0))},
                    {"label": "Listos", "value": str(counts.get("ready", 0))}],
        "bars": [{"label": r["name"], "value": f"{r['units']} u.", "pct": max(2, round(100 * r["units"] / top))} for r in rows[:5]],
    }


def answer_ready(venues):
    from operations.models import ServiceSession
    from sales.models import OrderItem

    rows = list(OrderItem.objects.filter(order__service_session__table__venue__in=venues, prep_status="ready",
                                         order__service_session__status=ServiceSession.Status.OPEN)
                .values("order__service_session__table__code").annotate(n=Count("id"))
                .order_by("order__service_session__table__code"))
    links = [_link("Abrir mapa de sala", "floor:map")]
    if not rows:
        return "No hay platos listos esperando ser servidos.", {"links": links}
    text = "🍽️ Listos para servir:\n" + "\n".join(
        f"• Mesa {r['order__service_session__table__code']}: {r['n']} plato(s)" for r in rows)
    return text, {"links": links, "metrics": [{"label": "Por servir", "value": str(sum(r["n"] for r in rows))}]}


def answer_floor(venues):
    from operations.services.floor import build_floor

    floor = build_floor(venues)
    counts = [(label, n) for label, _, n in floor["counts"]]
    parts = [f"{n} {label.lower()}" for label, n in counts if n]
    text = "🗺️ Sala: " + (", ".join(parts) if parts else "sin mesas activas") + f". {len(floor['waitlist'])} grupo(s) esperando mesa."
    alerts = [(card["table"].code, alert) for _, cards in floor["zones"] for card in cards for alert in card["alerts"]]
    if alerts:
        text += "\nPara atender:\n" + "\n".join(f"• Mesa {code}: {alert}" for code, alert in alerts[:6])
    metrics = [{"label": label, "value": str(n)} for label, n in counts[:4]]
    metrics.append({"label": "Esperando mesa", "value": str(len(floor["waitlist"]))})
    return text, {"links": [_link("Abrir mapa de sala", "floor:map")], "metrics": metrics}


def answer_cashier(venues):
    from operations.models import ServiceSession
    from operations.services.floor import PENDING, thermometer
    from sales.models import Order

    icons = {"verde": "🟢", "amarillo": "🟡", "rojo": "🔴"}
    lines, total, risk = [], 0, 0
    for session in ServiceSession.objects.filter(table__venue__in=venues, status=ServiceSession.Status.OPEN).select_related("table"):
        pending = list(Order.objects.filter(service_session=session, status__in=PENDING))
        if not pending and not session.bill_requested_at:
            continue
        amount = sum((order.total or 0) for order in pending)
        result = thermometer(session)
        total += amount
        risk += result["level"] == "rojo"
        lines.append(f"{icons[result['level']]} Mesa {session.table.code}: {_clp(amount)} por cobrar · {result['label']}. "
                     f"{result['suggestion']}")
    links = [_link("Abrir caja", "cashier:home")]
    if not lines:
        return "No hay mesas por cobrar en este momento.", {"links": links}
    return "💵 Caja ahora:\n" + "\n".join(lines), {"links": links, "metrics": [
        {"label": "Mesas por cobrar", "value": str(len(lines))},
        {"label": "Total por cobrar", "value": _clp(total)},
        {"label": "En riesgo", "value": str(risk), "tone": "down" if risk else "up"},
    ]}


def answer_cameras(venues):
    from ai_vision.services.camera_metrics import camera_measurements

    rows = camera_measurements(venues)
    links = [_link("Panel del supervisor", "supervisor:home")]
    if not rows:
        return "No hay cámaras activas registradas.", {"links": links}
    live = [r for r in rows if r["live"]]
    text = f"📷 Cámaras: {len(live)} de {len(rows)} con lecturas en vivo (últimos 15 min)."
    for r in rows[:6]:
        parts = [r["status"]]
        if r["ieo"] is not None:
            parts.append(f"IEO {r['ieo']:.0f}")
        if r["scene_people"] is not None:
            parts.append(f"{r['scene_people']:.0f} personas (YOLO26)")
        elif r["people"] is not None:
            parts.append(f"{_dec(r['people'])} rostros")
        if r["latency_ms"] is not None:
            parts.append(f"{r['latency_ms']:.0f} ms")
        text += f"\n• {r['camera'].name} (mesa {r['table']}): " + " · ".join(parts)
    from ai_vision.services.thumbs import camera_thumbs

    thumbs = [{k: t[k] for k in ("name", "ieo", "boxes", "people", "scene_people", "occupancy")}
              for t in camera_thumbs(venues, limit=6)]
    ieos = [r["ieo"] for r in rows if r["ieo"] is not None]
    latencies = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    return text, {"links": links, "thumbs": thumbs, "metrics": [
        {"label": "En vivo", "value": f"{len(live)}/{len(rows)}"},
        {"label": "IEO promedio", "value": f"{sum(ieos) / len(ieos):.0f}" if ieos else "—"},
        {"label": "Latencia", "value": f"{sum(latencies) / len(latencies):.0f} ms" if latencies else "—"},
    ], "bars": [{"label": r["camera"].name, "value": f"{r['ieo']:.0f}", "pct": max(2, round(r["ieo"]))}
                for r in rows if r["ieo"] is not None][:6]}


def answer_infrastructure(venues):
    from operations.models import EnvironmentReading, InfrastructureReport, SatisfactionEvaluation

    reports = list(InfrastructureReport.objects.filter(venue__in=venues, status="open")[:5])
    scores = SatisfactionEvaluation.objects.filter(
        service_session__table__venue__in=venues, service_session__started_at__gte=timezone.now() - timedelta(days=7),
    ).aggregate(c=Avg("cleanliness_rating"), r=Avg("restroom_rating"), a=Avg("ambience_rating"))
    reading = EnvironmentReading.objects.filter(venue__in=venues).first()
    text = "🛠️ Infraestructura:"
    if reports:
        text += f"\n• {len(reports)} incidencia(s) abiertas: " + "; ".join(f"{r.get_area_display()} ({r.description})" for r in reports)
    else:
        text += "\n• Sin incidencias abiertas."
    if reading:
        text += (f"\n• Último registro ambiental ({reading.zone}, {timezone.localtime(reading.recorded_at):%d-%m %H:%M}): "
                 f"luz {reading.lighting or '—'}/5, ruido {reading.noise or '—'}/5"
                 + (f", {_dec(float(reading.temperature_c))} °C." if reading.temperature_c is not None else "."))
    text += f"\n• Opiniones del QR (7 días): limpieza {_dec(scores['c'])}, baños {_dec(scores['r'])}, ambiente {_dec(scores['a'])}."
    return text, {"links": [_link("Panel del supervisor", "supervisor:home")], "metrics": [
        {"label": "Limpieza", "value": _dec(scores["c"])}, {"label": "Baños", "value": _dec(scores["r"])},
        {"label": "Ambiente", "value": _dec(scores["a"])}, {"label": "Incidencias", "value": str(len(reports))},
    ]}


def answer_role_help(profile):
    from authentication.roles import role_key

    from .role_scope import ROLE_CHIPS, ROLE_HELP

    key = role_key(profile)
    examples = " · ".join(f"«{prompt}»" for _, prompt in ROLE_CHIPS.get(key, []))
    return (f"Como {profile.get_role_display().lower()} puedo ayudarte con {ROLE_HELP.get(key, 'las funciones de tu rol')}."
            + (f"\nPrueba con: {examples}" if examples else "")), {"links": []}


def answer_how_it_works():
    return ("🧠 Soy Sazón, un módulo propio de GastroInsight AI. Técnicamente soy una interfaz de lenguaje natural a "
            "bases de datos (NLIDB) basada en reglas: identifico la intención de tu pregunta y ejecuto consultas "
            "predefinidas y parametrizadas sobre los datos de tu local.\n"
            "• No uso modelos de lenguaje externos, no envío datos a terceros y no tengo costo por consulta.\n"
            "• Las ideas del inicio no son predicciones: son reglas de negocio y estadística descriptiva "
            "(promedios, variación semanal, análisis de canasta y correlaciones). Cada una muestra cómo se calculó.\n"
            "• La visión usa YOLO26 (personas y mesas), YuNet (rostros) y FER+ (expresiones), en este equipo y sin guardar imágenes."), {
        "links": [{"label": "Ver cómo funciona", "url": reverse("vision:how_it_works")}]}
