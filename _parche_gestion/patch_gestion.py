"""Centro de gestión v2: advertencias contraídas, pestañas amigables, ventanas flotantes,
interruptores en lugar de casillas y Detectar cámaras guiado. Repetible."""
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
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC / nombre, dst)
    print(f"[OK] {destino}")


def reemplazar(ruta, pares, etiqueta):
    path = ROOT / ruta
    text, nl = leer(path)
    cambios = 0
    for viejo, nuevo in pares:
        if nuevo in text:
            continue
        if viejo in text:
            text = text.replace(viejo, nuevo.replace("\n", nl))
            cambios += 1
        else:
            errores.append(f"{etiqueta}: ancla no encontrada -> {viejo[:60]}")
            print(f"[REVISAR] {etiqueta}")
            return
    escribir(path, text)
    print(f"[OK] {etiqueta}" if cambios else f"[ya aplicado] {etiqueta}")


copiar("home.html", TPL + "home.html", "data-mgmt-v2")
copiar("staff_edit.html", TPL + "staff_edit.html", "staff-edit-head")
copiar("camera_discover.html", TPL + "camera_discover.html", "data-discover-v2")
copiar("_camera_assign.html", TPL + "_camera_assign.html", "assign-v2")
copiar("_field.html", TPL + "_field.html", "mgmt-switch-ui")
copiar("mgmt_ui.js", "static/js/mgmt_ui.js", "data-mgmt-chips")
copiar("test_management_ui.py", "core/test_management_ui.py", "class ManagementUiTests")

reemplazar("authentication/views_management.py", [
    ('"venues_list": venues,', '"venues_list": venues, "role_guide": _role_guide(actor),'),
    ("def _alert_forms(venues):",
     "def _role_guide(actor):\n"
     "    \"\"\"Qué puede hacer cada rol que este administrador puede asignar (para la ayuda de Personal).\"\"\"\n"
     "    from .forms_management import LABELS, assignable_roles\n"
     "    from .roles import PROFILE_CAPABILITIES\n"
     "\n"
     "    return [{\"key\": r, \"label\": LABELS.get(r, r), \"caps\": [cap for cap, roles in PROFILE_CAPABILITIES if r in roles]}\n"
     "            for r in assignable_roles(actor)]\n"
     "\n"
     "\n"
     "def _alert_forms(venues):"),
], "vista: guía de roles")

reemplazar("static/js/sec_center.js", [
    ('const KEY = "gi-sec-collapsed";', 'const KEY = "gi-sec-open"; // contraídas por defecto'),
    ('collapsed ? "Mostrar ▾" : "Ocultar ▴"', 'collapsed ? "Ver detalles ▾" : "Ocultar ▴"'),
    ('localStorage.setItem(KEY, collapsed ? "1" : "0")', 'localStorage.setItem(KEY, collapsed ? "0" : "1")'),
    ('if (localStorage.getItem(KEY) === "1") setCollapsed(true);', 'if (localStorage.getItem(KEY) === "1") setCollapsed(false);'),
], "sec_center.js: contraídas por defecto")

base = ROOT / "templates/base.html"
text, nl = leer(base)
if "js/mgmt_ui.js" not in text:
    ancla = "<script src=\"{% static 'js/sec_center.js' %}?v=1\"></script>"
    if ancla in text:
        text = text.replace(ancla, "<script src=\"{% static 'js/sec_center.js' %}?v=2\"></script>" + nl
                            + "    <script src=\"{% static 'js/mgmt_ui.js' %}?v=1\"></script>")
        print("[OK] base.html: scripts")
    else:
        errores.append("base.html: ancla de sec_center.js")
        print("[REVISAR] base.html: scripts")
else:
    print("[ya aplicado] base.html: scripts")
if "css/theme.css' %}?v=95" in text:
    print("[ya aplicado] base.html: theme.css v95")
elif "css/theme.css' %}?v=94" in text:
    text = text.replace("css/theme.css' %}?v=94", "css/theme.css' %}?v=95")
    print("[OK] base.html: theme.css v95")
else:
    errores.append("base.html: versión de theme.css")
    print("[REVISAR] base.html: versión de theme.css")
escribir(base, text)

css = ROOT / "static/css/theme.css"
text, nl = leer(css)
if "Centro de gestión v2: pestañas amigables" in text:
    print("[ya aplicado] theme.css")
else:
    escribir(css, text.rstrip() + nl + (SRC / "mgmt.css").read_text(encoding="utf-8").replace("\n", nl))
    print("[OK] theme.css")

if errores:
    print("ERRORES:", *errores, sep="\n - ")
    sys.exit(1)
print("Listo: Centro de gestión v2 aplicado.")
