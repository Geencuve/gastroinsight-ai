"""CR-01 v3: telemetria exige politica habilitada y autorizacion vigente. Tolera saltos de linea mixtos."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(__file__).resolve().parent
api = ROOT / "operations" / "api.py"
text = api.read_bytes().decode("utf-8-sig")

# 1. Funcion que reutiliza privacy.PrivacyPolicy.is_processing_authorized
if "def _vision_authorized(" in text:
    print("[ya aplicado] funcion _vision_authorized")
else:
    m = re.search(r"(\r?\n)def _endpoint\(handler\):", text)
    if not m:
        print("[REVISAR] no encontre 'def _endpoint(handler):'")
        sys.exit(1)
    nl = m.group(1)
    bloque = nl.join([
        "def _vision_authorized(venue):",
        '    """CR-01: misma regla que la visi\u00f3n local: pol\u00edtica habilitada, sin im\u00e1genes y autorizaci\u00f3n vigente."""',
        "    from privacy.models import PrivacyPolicy",
        "",
        '    policy = PrivacyPolicy.objects.filter(venue=venue).prefetch_related("authorizations").first()',
        "    return bool(policy and policy.is_processing_authorized)",
        "", "", "",
    ])
    text = text[:m.start() + len(nl)] + bloque + text[m.start() + len(nl):]
    print("[OK] funcion _vision_authorized")

# 2. Control dentro de telemetry, antes de 'table = camera.table'
if "if not _vision_authorized(key.venue):" in text:
    print("[ya aplicado] control en telemetry")
else:
    inicio = text.find("def telemetry(")
    m = re.compile(r"(\r?\n)    table = camera\.table\r?\n").search(text, inicio)
    if inicio < 0 or not m:
        print("[REVISAR] no encontre 'table = camera.table' dentro de telemetry")
        sys.exit(1)
    nl = m.group(1)
    control = nl.join([
        "",
        "    if not _vision_authorized(key.venue):",
        '        raise ApiError(403, "El local no tiene una pol\u00edtica de privacidad habilitada con una "',
        '                            "autorizaci\u00f3n vigente: la lectura no se guard\u00f3.")',
    ])
    text = text[:m.start()] + control + text[m.start():]
    print("[OK] control en telemetry")

api.write_bytes(text.encode("utf-8"))
(ROOT / "operations" / "test_api_cr01.py").write_text((SRC / "test_api_cr01.py").read_text(encoding="utf-8"), encoding="utf-8")
print("[OK] operations\\test_api_cr01.py")
print("Listo: CR-01 aplicado.")