"""CR-01: las pruebas existentes de la API crean politica y autorizacion vigentes en su setUp."""
import re
import sys
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "operations" / "test_api.py"
text = path.read_bytes().decode("utf-8-sig")

if "CR-01: el local de prueba" in text:
    print("[ya aplicado] setUp de IntegrationApiTests")
    sys.exit(0)

clase = text.find("class IntegrationApiTests")
setup = re.compile(r"\n    def setUp\(self\):\r?\n").search(text, clase) if clase >= 0 else None
fin = re.compile(r"(\r?\n)(\r?\n)*    def ").search(text, setup.end()) if setup else None
if not setup or not fin:
    print("[REVISAR] no encontre el setUp de IntegrationApiTests")
    sys.exit(1)
if "self.camera" not in text[setup.end():fin.start()]:
    print("[REVISAR] el setUp no crea self.camera; pegame operations/test_api.py")
    sys.exit(1)

nl = fin.group(1)
lineas = [
    "        # CR-01: el local de prueba necesita pol\u00edtica habilitada y autorizaci\u00f3n vigente para enviar telemetr\u00eda.",
    "        from privacy.models import PrivacyPolicy, ProcessingAuthorization",
    "",
    "        politica, _ = PrivacyPolicy.objects.get_or_create(",
    '            venue=self.camera.venue, defaults={"purpose": "Indicadores agregados por mesa"})',
    "        PrivacyPolicy.objects.filter(pk=politica.pk).update(processing_enabled=True, store_original_images=False)",
    '        ProcessingAuthorization.objects.create(privacy_policy=politica, source_description="Salon principal")',
]
bloque = nl + nl.join(lineas)
text = text[:fin.start()] + bloque + text[fin.start():]
path.write_bytes(text.encode("utf-8"))
print("[OK] setUp de IntegrationApiTests con autorizacion vigente")