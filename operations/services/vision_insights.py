"""
Recomendaciones alimentadas por la visión y la operación (K2): reacción a los platos, experiencia por etapa
del journey, abandonos de la lista de espera y mesas poco usadas. Todas son estadística descriptiva.
"""
from datetime import timedelta
from statistics import median

from django.db.models import Count
from django.utils import timezone


def _fmt(value, digits=2):
    return f"{value:+.{digits}f}".replace(".", ",")


def vision_insights(venues, days=14):
    from core.services.insights import _item

    items = {"marketing": [], "servicio": []}

    # Reacción a los platos (IBE antes y después de servirlos)
    try:
        from sales.services.kitchen import acceptance

        rows = [r for station in ("cocina", "barra") for r in acceptance(venues, station)
                if r.get("ibe_delta") is not None and (r.get("units") or 0) >= 3]
    except Exception:  # noqa: BLE001 — la sección no debe romper el inicio
        rows = []
    if rows:
        best = max(rows, key=lambda r: r["ibe_delta"])
        worst = min(rows, key=lambda r: r["ibe_delta"])
        if best["ibe_delta"] > 0.05:
            items["marketing"].append(_item(
                "😄", f"«{best['name']}» es el plato que más alegra a las mesas",
                f"El balance de expresiones sube {_fmt(best['ibe_delta'])} al servirlo ({best['units']} unidades).",
                "Destácalo en la carta y en redes: es tu mejor carta de presentación.", "kitchen:home", score=70))
        if worst["ibe_delta"] < -0.05:
            items["servicio"].append(_item(
                "😕", f"«{worst['name']}» provoca una reacción negativa al servirlo",
                f"El balance de expresiones baja {_fmt(worst['ibe_delta'])} después de recibirlo ({worst['units']} unidades).",
                "Revisa presentación, temperatura y tiempo de salida de cocina de este plato.", "kitchen:home", score=82))
        middle = median(r["units"] for r in rows)
        popular_bad = [r for r in rows if r["units"] >= middle and r["ibe_delta"] < -0.05 and r is not worst]
        if popular_bad:
            dish = popular_bad[0]
            items["servicio"].append(_item(
                "🤔", f"«{dish['name']}» se vende mucho pero no convence",
                f"Está entre los más pedidos, pero el balance de expresiones baja {_fmt(dish['ibe_delta'])} al servirlo.",
                "Prueba ajustes en la receta o en la porción: un plato popular que decepciona afecta la recomendación del local.",
                "kitchen:home", score=78))

    # Experiencia por etapa del journey
    from operations.services.journey import journey_stats

    stages = [s for s in journey_stats(venues, days) if s["ieo"] is not None and s["n"] >= 5]
    if len(stages) >= 2:
        low, high = min(stages, key=lambda s: s["ieo"]), max(stages, key=lambda s: s["ieo"])
        if high["ieo"] - low["ieo"] >= 5:
            items["servicio"].append(_item(
                "🧭", f"La experiencia cae en la etapa «{low['label']}»",
                f"IEO promedio {low['ieo']:.0f} frente a {high['ieo']:.0f} en «{high['label']}» ({low['n']} atenciones, {days} días).",
                low["action"], "supervisor:home", score=85))

    # Abandonos de la lista de espera
    from operations.models import RestaurantTable, ServiceSession, WaitlistEntry

    since = timezone.now() - timedelta(days=days)
    waiting = WaitlistEntry.objects.filter(venue__in=venues, arrived_at__gte=since)
    total, gone = waiting.count(), waiting.filter(cancelled=True).count()
    if total >= 5 and gone / total >= 0.15:
        items["servicio"].append(_item(
            "🚶", f"El {round(100 * gone / total)}% de los grupos en espera se va sin sentarse",
            f"{gone} de {total} grupos registrados en la lista de espera se retiraron ({days} días).",
            "Ofrece una estimación de espera al llegar y algo para beber mientras esperan.", "floor:map", score=80))

    # Mesas poco usadas (ubicación, sol, ruido)
    usage = {row["table_id"]: row["n"] for row in ServiceSession.objects.filter(
        table__venue__in=venues, started_at__gte=timezone.now() - timedelta(days=28)).values("table_id").annotate(n=Count("id"))}
    tables = list(RestaurantTable.objects.filter(venue__in=venues, is_active=True))
    if len(tables) >= 3 and usage:
        average = sum(usage.get(t.id, 0) for t in tables) / len(tables)
        avoided = sorted((t for t in tables if average >= 3 and usage.get(t.id, 0) < 0.4 * average), key=lambda t: usage.get(t.id, 0))
        if avoided:
            codes = ", ".join(t.code for t in avoided[:3])
            items["servicio"].append(_item(
                "☀️", f"Mesas que se usan poco: {codes}",
                f"Se ocupan menos del 40% que el promedio del local ({average:.1f} atenciones por mesa en 28 días).",
                "Revisa si les llega sol directo, ruido, corriente de aire o si están mal ubicadas.", "floor:map", score=60))
    return items
