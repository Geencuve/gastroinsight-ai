"""Centro de gestión: advertencias de seguridad accionables y estilo unificado.
Repetible: imprime [OK], [ya aplicado] o [REVISAR]."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(__file__).resolve().parent
errores = []


def leer(path):
    data = path.read_bytes().decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in data else "\n"
    return data, nl


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


copiar("security_checks.py", "core/security_checks.py", "security_warnings_detailed")
copiar("configurar_env.py", "core/management/commands/configurar_env.py", "def actualizar_env")
copiar("test_security_center.py", "core/test_security_center.py", "class ConfigurarEnvTests")
copiar("sec_center.js", "static/js/sec_center.js", "sec-fix-")

# Plantilla del Centro de gestión
tpl = ROOT / "authentication/templates/authentication/management/home.html"
text, nl = leer(tpl)
if 'id="sec-panel"' in text:
    print("[ya aplicado] plantilla: advertencias")
else:
    start = text.find("{% if security_warnings %}")
    fin_ancla = "{{ kpis.entrances }} de entrada</small></article>"
    end = text.find(fin_ancla)
    end = text.find("</div>", end) + len("</div>") if end != -1 else -1
    if start == -1 or end <= start:
        errores.append("plantilla: no se encontró el bloque de advertencias e indicadores")
        print("[REVISAR] plantilla: bloque de advertencias")
    else:
        nuevo = (SRC / "bloque_seguridad.html").read_text(encoding="utf-8").rstrip("\n").replace("\n", nl)
        text = text[:start] + nuevo + text[end:]
        print("[OK] plantilla: advertencias e indicadores")
if 'class="card page-panel mgmt-panel"' in text:
    print("[ya aplicado] plantilla: recuadro de pestañas")
else:
    a = '<div data-tabs="gestion">'
    b = "</div>" + nl + "{% endblock %}"
    if text.count(a) == 1 and text.rstrip().endswith(b):
        text = text.replace(a, '<section class="card page-panel mgmt-panel">' + nl + a)
        idx = text.rfind(b)
        text = text[:idx] + "</div>" + nl + "</section>" + nl + "{% endblock %}" + text[idx + len(b):]
        print("[OK] plantilla: recuadro de pestañas")
    else:
        errores.append("plantilla: anclas del recuadro de pestañas")
        print("[REVISAR] plantilla: recuadro de pestañas")
escribir(tpl, text)

# Vista
view = ROOT / "authentication/views_management.py"
text, nl = leer(view)
viejo = '"security_warnings": __import__("core.security_checks", fromlist=["x"]).security_warnings(),'
nuevo = ('"security_warnings": __import__("core.security_checks", fromlist=["x"]).security_warnings_detailed('
         'request.user, {u.pk for u in users}),')
if nuevo in text:
    print("[ya aplicado] vista")
elif viejo in text:
    escribir(view, text.replace(viejo, nuevo))
    print("[OK] vista")
else:
    errores.append("vista: ancla de security_warnings")
    print("[REVISAR] vista")

# base.html: script nuevo y versión de estilos
base = ROOT / "templates/base.html"
text, nl = leer(base)
if "js/sec_center.js" in text:
    print("[ya aplicado] base.html: script")
else:
    ancla = "<script src=\"{% static 'js/promo_ui.js' %}?v=1\"></script>"
    if ancla in text:
        text = text.replace(ancla, ancla + nl + "    <script src=\"{% static 'js/sec_center.js' %}?v=1\"></script>")
        print("[OK] base.html: script")
    else:
        errores.append("base.html: ancla de promo_ui.js")
        print("[REVISAR] base.html: script")
if "css/theme.css' %}?v=94" in text:
    print("[ya aplicado] base.html: theme.css v94")
elif "css/theme.css' %}?v=93" in text:
    text = text.replace("css/theme.css' %}?v=93", "css/theme.css' %}?v=94")
    print("[OK] base.html: theme.css v94")
else:
    errores.append("base.html: versión de theme.css")
    print("[REVISAR] base.html: versión de theme.css")
escribir(base, text)

# Estilos
css = ROOT / "static/css/theme.css"
text, nl = leer(css)
if "Centro de gestión: advertencias de seguridad accionables" in text:
    print("[ya aplicado] theme.css")
else:
    extra = (SRC / "sec_center.css").read_text(encoding="utf-8")
    escribir(css, text.rstrip() + nl + extra.replace("\n", nl))
    print("[OK] theme.css")

if errores:
    print("ERRORES:", *errores, sep="\n - ")
    sys.exit(1)
print("Listo: parche de seguridad aplicado.")
