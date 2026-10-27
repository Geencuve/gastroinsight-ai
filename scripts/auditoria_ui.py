"""Auditoría automática de la interfaz: errores visibles, textos, imágenes y tiempos de respuesta."""
import logging
import os
import re
import statistics
import time
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.contrib.auth.models import User  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import URLPattern, URLResolver, get_resolver, reverse  # noqa: E402

from ai_vision.models import AnalysisSession  # noqa: E402
from cameras.models import Camera  # noqa: E402
from menus.models import Menu  # noqa: E402
from operations.feedback import table_token  # noqa: E402
from operations.models import ServiceSession  # noqa: E402
from sales.models import Order  # noqa: E402
from venues.models import Venue  # noqa: E402

logging.disable(logging.WARNING)

SKIP = ("logout", "delete", "eliminar", "stream", "feed", "video", "live", "start", "stop", "preview", "pay",
        "confirm", "cancel", "close", "resolve", "review", "continue", "message", "add", "discount", "image",
        "create_session")
ISSUES = [
    (r">\s*None\s*<", "Se muestra 'None'"),
    (r"\$None|None\s*%", "Monto o porcentaje 'None'"),
    (r"\{\{|\{%", "Etiqueta de plantilla sin procesar"),
    (r">\s*nan\s*<|\bnan%", "Valor 'nan'"),
    (r"This field is required|Enter a valid|Select a valid", "Mensaje de Django en inglés"),
    (r"Traceback \(most recent call", "Traza de error visible"),
]
WARNINGS = [
    (r"emoci[oó]n|emociones", "Terminología: usar 'expresión' en lugar de 'emoción'"),
    (r'style="[^"]*background(-color)?\s*:\s*(#fff\b|#ffffff|white)', "Fondo blanco fijo en atributo style"),
    (r'class="[^"]*\b(d-flex|text-muted|mb-4|py-4|btn-outline-primary|form-label)\b', "Clase de Bootstrap sin estilo"),
]


def walk(patterns, prefix="", ns=""):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from walk(p.url_patterns, prefix + str(p.pattern), f"{ns}{p.namespace}:" if p.namespace else ns)
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern), f"{ns}{p.name or '-'}"


def staff_urls():
    urls = []
    for route, name in walk(get_resolver().url_patterns):
        if route.startswith("admin/") and route != "admin/":
            continue
        if any(ch in route for ch in "<^$(?"):
            continue
        short = name.split(":")[-1].lower()
        if any(s in short or s in route.lower() for s in SKIP):
            continue
        urls.append("/" + route)
    venue = Venue.objects.filter(is_active=True).first()
    menu = Menu.objects.filter(is_active=True).first()
    if menu:
        urls.append(reverse("menus:detail", args=[menu.id]))
    if venue:
        urls += [reverse("reports:daily", args=[venue.id]), reverse("reports:period", args=[venue.id]) + "?period=month"]
    for order in (Order.objects.order_by("-id").first(), Order.objects.filter(status="OPEN").order_by("-id").first()):
        if order:
            urls.append(reverse("sales:order_detail", args=[order.id]))
    for session in (
        AnalysisSession.objects.exclude(camera__source_type=Camera.SourceType.DEMO).order_by("-id").first(),
        AnalysisSession.objects.filter(camera__source_type=Camera.SourceType.DEMO).order_by("-id").first(),
    ):
        if session:
            urls.append(reverse("ai_vision:session_detail", args=[session.id]))
    urls += [reverse("core:promo_generator") + "?tipo=combo", reverse("core:promo_generator") + "?tipo=dia&formato=historia"]
    return sorted(set(urls)) + public_urls()


def public_urls():
    urls = ["/", "/auth/login/"]
    venue = Venue.objects.filter(is_active=True).first()
    if venue:
        urls += [reverse("menus:public", args=[venue.id]), reverse("assistant_chat:customer_chat", args=[venue.id])]
    session = ServiceSession.objects.filter(status="open").select_related("table").first()
    if session:
        urls.append(reverse("feedback:form", args=[table_token(session.table)]))
    return urls


def audit(client, url, media_cache):
    start = time.perf_counter()
    try:
        response = client.get(url)
    except Exception as error:  # noqa: BLE001
        return (time.perf_counter() - start) * 1000, "EXC", [f"{type(error).__name__}: {error}"], []
    ms = (time.perf_counter() - start) * 1000
    status = response.status_code
    if status in (301, 302) or "html" not in response.get("Content-Type", ""):
        return ms, status, [], []
    html = response.content.decode("utf-8", "ignore")
    visible = re.sub(r"<(script|style)\b.*?</\1>", "", html, flags=re.S | re.I)
    issues = [label for pattern, label in ISSUES if re.search(pattern, visible)]
    warnings = [label for pattern, label in WARNINGS if re.search(pattern, visible, re.I)]
    if status >= 400:
        issues.insert(0, f"HTTP {status}")
    for src in list(dict.fromkeys(re.findall(r'src="(/media/[^"]+)"', html)))[:6]:
        if src not in media_cache:
            media_cache[src] = client.get(src).status_code
        if media_cache[src] != 200:
            issues.append(f"Imagen rota: {src}")
    return ms, status, issues, warnings


def main():
    media_cache, times, problems, warns = {}, [], [], []
    profiles = [
        ("admin_demo", User.objects.filter(username="admin_demo").first(), staff_urls()),
        ("operador_demo", User.objects.filter(username="operador_demo").first(), staff_urls()),
        ("visitante", None, public_urls()),
    ]
    for label, user, urls in profiles:
        client = Client(HTTP_HOST="127.0.0.1")
        if user:
            client.force_login(user)
        print(f"\n##### {label}: {len(urls)} pantallas #####")
        for url in urls:
            ms, status, issues, warnings = audit(client, url, media_cache)
            times.append((ms, label, url))
            mark = "OK " if not issues else "!! "
            print(f"{mark}{status}  {ms:7.0f} ms  {url}")
            for item in issues:
                problems.append(f"[{label}] {url} -> {item}")
                print(f"      PROBLEMA: {item}")
            for item in warnings:
                warns.append(f"[{label}] {url} -> {item}")

    values = [t[0] for t in times]
    print("\n===== RESUMEN =====")
    print(f"Pantallas revisadas: {len(times)} | problemas: {len(problems)} | advertencias: {len(warns)}")
    print(f"Tiempo de respuesta: promedio {statistics.mean(values):.0f} ms | mediana {statistics.median(values):.0f} ms | "
          f"máximo {max(values):.0f} ms | bajo 1 s: {100 * sum(v < 1000 for v in values) / len(values):.0f}%")
    print("Más lentas:")
    for ms, label, url in sorted(times, reverse=True)[:5]:
        print(f"   {ms:7.0f} ms  [{label}] {url}")
    print("\n===== PROBLEMAS =====")
    print("\n".join(problems) or "Ninguno")
    print("\n===== ADVERTENCIAS (únicas) =====")
    print("\n".join(sorted(set(w.split("] ", 1)[1] for w in warns))) or "Ninguna")

    print("\n===== COLORES CLAROS FIJOS EN PLANTILLAS =====")
    light = re.compile(r"background(-color)?\s*:\s*(#fff\b|#ffffff|white|#f8fafc|#eff6ff|#fffbeb|#fff7ed)", re.I)
    for path in sorted(Path(".").glob("**/templates/**/*.html")):
        if "venv" in path.parts:
            continue
        hits = [i + 1 for i, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines()) if light.search(line)]
        if hits:
            print(f"{path}: líneas {hits[:12]}")


if __name__ == "__main__":
    main()
