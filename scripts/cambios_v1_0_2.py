"""Aplica los cambios de la versión 1.0.2 sobre el código actual."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"venv", "build", "dist", "evidencias", "staticfiles", "media", ".git", "migrations", "node_modules"}
errores = []


def load(path):
    raw = path.read_text(encoding="utf-8-sig")
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def save(path, text, crlf):
    path.write_text(text.replace("\n", "\r\n") if crlf else text, encoding="utf-8", newline="")


def replace_once(rel, old, new):
    path = ROOT / rel
    text, crlf = load(path)
    if text.count(old) != 1:
        errores.append(f"{rel}: se esperaba 1 coincidencia de {old[:60]!r}, hay {text.count(old)}")
        return
    save(path, text.replace(old, new), crlf)
    print(f"[OK] {rel}")


# 1. Correlación: excluir cámaras demo por defecto
replace_once("analytics/correlation_views.py",
             '    include_synthetic = request.GET.get("synthetic", "1") != "0"\n',
             '    # v1.0.2: por defecto se excluyen las cámaras demo (datos sintéticos); se incluyen con ?synthetic=1\n'
             '    include_synthetic = request.GET.get("synthetic", "0") == "1"\n')

# 2. Pruebas de correlación
T = "analytics/test_correlation.py"
replace_once(T, 'response = self.client.get("/analytics/correlation/")',
             'response = self.client.get("/analytics/correlation/?synthetic=1")')
replace_once(T, 'csv_response = self.client.get("/analytics/correlation/csv/")',
             'csv_response = self.client.get("/analytics/correlation/csv/?synthetic=1")')
path = ROOT / T
text, crlf = load(path)
if "test_panel_excluye_camaras_demo_por_defecto" not in text:
    text = text.rstrip("\n") + '''

    def test_panel_excluye_camaras_demo_por_defecto(self):
        for minutes, happy in ((40, 20), (60, 15), (80, 10), (100, 5)):
            self._session_with_events(minutes, {"happy": happy, "neutral": 30 - happy})
        self.client.force_login(self.user)
        response = self.client.get("/analytics/correlation/")
        self.assertFalse(response.context["include_synthetic"])
        self.assertEqual(response.context["rows"], [])
        response = self.client.get("/analytics/correlation/?synthetic=1")
        self.assertTrue(response.context["include_synthetic"])
        self.assertEqual(len(response.context["rows"]), 4)
'''
    save(path, text, crlf)
    print(f"[OK] {T} :: prueba de exclusión por defecto")

# 3. "prototipo" -> "Testbed experimental" en la interfaz y los textos legales
targets = [p for p in ROOT.rglob("*.html") if not SKIP & set(p.relative_to(ROOT).parts)]
targets += [ROOT / "core" / name for name in ("legal.py", "views_legal.py", "views_setup.py")]
targets += [p for p in ROOT.rglob("test*.py") if not SKIP & set(p.relative_to(ROOT).parts)]
total = 0
for path in targets:
    if not path.exists():
        continue
    text, crlf = load(path)
    new = re.sub(r"\b[Pp]rototipos\b", "Testbeds experimentales", text)
    new = re.sub(r"\b[Pp]rototipo\b", "Testbed experimental", new)
    if new != text:
        count = len(re.findall(r"\b[Pp]rototipos?\b", text))
        total += count
        save(path, new, crlf)
        print(f"[OK] {path.relative_to(ROOT)} :: {count} reemplazo(s)")
print(f"Total de reemplazos de 'prototipo': {total}")

# 4. Versión 1.0.2
replace_count = 0
for rel, pattern, value in (("desktop/installer.iss", r'#define AppVersion ".*?"', '#define AppVersion "1.0.2"'),
                            ("templates/base.html", r"(<strong>GastroInsight AI</strong> · )v[\d.]+", r"\g<1>v1.0.2")):
    path = ROOT / rel
    text, crlf = load(path)
    new, n = re.subn(pattern, value, text, count=1)
    if n:
        save(path, new, crlf)
        print(f"[OK] {rel} :: versión 1.0.2")
    else:
        errores.append(f"{rel}: no se encontró el número de versión")

if errores:
    print("\nERRORES:\n  " + "\n  ".join(errores))
    raise SystemExit(1)
