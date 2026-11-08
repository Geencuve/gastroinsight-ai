"""Tutorial de la API de integración: página nueva enlazada desde Integraciones. Repetible."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(__file__).resolve().parent
TPL = "authentication/templates/authentication/management/"
errores = []


def leer(path):
    data = path.read_bytes().decode("utf-8-sig")
    return data, ("\r\n" if "\r\n" in data else "\n")


def escribir(path, text):
    path.write_bytes(text.encode("utf-8"))


def copiar(nombre, destino, marca):
    dst = ROOT / destino
    if dst.exists() and marca in dst.read_text(encoding="utf-8-sig"):
        print(f"[ya aplicado] {destino}")
        return
    shutil.copyfile(SRC / nombre, dst)
    print(f"[OK] {destino}")


def reemplazar(ruta, pares, etiqueta):
    path = ROOT / ruta
    text, nl = leer(path)
    cambios = 0
    for viejo, nuevo, marca in pares:
        if marca in text:
            continue
        if viejo not in text:
            errores.append(f"{etiqueta}: ancla no encontrada -> {viejo[:70]}")
            print(f"[REVISAR] {etiqueta}")
            return
        text = text.replace(viejo, nuevo.replace("\n", nl), 1)
        cambios += 1
    escribir(path, text)
    print(f"[OK] {etiqueta}" if cambios else f"[ya aplicado] {etiqueta}")


copiar("api_tutorial.html", TPL + "api_tutorial.html", "data-api-tutorial")
copiar("api_tutorial.js", "static/js/api_tutorial.js", "data-tut-try")
copiar("test_api_tutorial.py", "core/test_api_tutorial.py", "class ApiTutorialTests")

# Vista
view = ROOT / "authentication/views_management.py"
text, nl = leer(view)
if "def api_tutorial(" in text:
    print("[ya aplicado] vista api_tutorial")
else:
    snippet = (SRC / "view_snippet.py").read_text(encoding="utf-8")
    escribir(view, text.rstrip() + nl + snippet.replace("\n", nl))
    print("[OK] vista api_tutorial")

# Ruta
reemplazar("authentication/management_urls.py", [(
    '    path("api/nueva/", views_management.api_key_create, name="api_key_create"),',
    '    path("api/nueva/", views_management.api_key_create, name="api_key_create"),\n'
    '    path("api/tutorial/", views_management.api_tutorial, name="api_tutorial"),',
    'name="api_tutorial"')], "ruta /gestion/api/tutorial/")

# Enlaces desde la pestaña Integraciones
reemplazar(TPL + "home.html", [
    ('<button type="button" class="btn btn-primary mgmt-add" data-open-dialog="dlg-api">＋ Nueva clave</button>',
     '<a class="btn mgmt-add" href="{% url \'management:api_tutorial\' %}">📘 Tutorial de la API</a>\n'
     '            <button type="button" class="btn btn-primary mgmt-add" data-open-dialog="dlg-api">＋ Nueva clave</button>',
     "📘 Tutorial de la API</a>"),
    ('<li><b>3</b>Pégala en el otro sistema</li>\n        </ol>',
     '<li><b>3</b>Pégala en el otro sistema</li>\n        </ol>\n'
     '        <p class="mgmt-tip tut-cta">📘 ¿Primera vez? Sigue el <a href="{% url \'management:api_tutorial\' %}">tutorial paso a paso</a>: '
     'ejemplos listos para copiar con los datos de tu local (PowerShell, Python, JavaScript o curl) y un botón para probar la conexión.</p>',
     'class="mgmt-tip tut-cta"'),
    ('Solo se guarda su huella SHA-256 y puedes revocarla cuando quieras.</p>',
     'Solo se guarda su huella SHA-256 y puedes revocarla cuando quieras. '
     '¿Cómo usarla? Mira el <a href="{% url \'management:api_tutorial\' %}">📘 tutorial</a>.</p>',
     "¿Cómo usarla? Mira el"),
], "home.html: enlaces al tutorial")

# base.html
base = ROOT / "templates/base.html"
text, nl = leer(base)
if "js/api_tutorial.js" in text:
    print("[ya aplicado] base.html: script")
else:
    ancla = "<script src=\"{% static 'js/mgmt_ui.js' %}?v=1\"></script>"
    if ancla in text:
        text = text.replace(ancla, ancla + nl + "    <script src=\"{% static 'js/api_tutorial.js' %}?v=1\"></script>")
        print("[OK] base.html: script")
    else:
        errores.append("base.html: ancla de mgmt_ui.js")
        print("[REVISAR] base.html: script")
if "css/theme.css' %}?v=96" in text:
    print("[ya aplicado] base.html: theme.css v96")
elif "css/theme.css' %}?v=95" in text:
    text = text.replace("css/theme.css' %}?v=95", "css/theme.css' %}?v=96")
    print("[OK] base.html: theme.css v96")
else:
    errores.append("base.html: versión de theme.css")
    print("[REVISAR] base.html: versión de theme.css")
escribir(base, text)

css = ROOT / "static/css/theme.css"
text, nl = leer(css)
if "Tutorial de la API de integración" in text:
    print("[ya aplicado] theme.css")
else:
    escribir(css, text.rstrip() + nl + (SRC / "tut.css").read_text(encoding="utf-8").replace("\n", nl))
    print("[OK] theme.css")

if errores:
    print("ERRORES:", *errores, sep="\n - ")
    sys.exit(1)
print("Listo: tutorial de la API agregado.")
