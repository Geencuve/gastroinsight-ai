"""Resume pruebas.log y cobertura.json para la tabla 12.3 del informe."""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

folder = Path(sys.argv[1] if len(sys.argv) > 1 else "evidencias/E03")
log = (folder / "pruebas.log").read_text(encoding="utf-8", errors="replace")
ran = re.search(r"Ran (\d+) tests? in ([\d.]+)s", log)
final = re.findall(r"^(OK|FAILED)(?: \(([^)]*)\))?\s*$", log, re.M)
total, seconds = (int(ran.group(1)), float(ran.group(2))) if ran else (0, 0.0)
counts = defaultdict(int)
if final and final[-1][1]:
    for part in final[-1][1].split(","):
        key, _, value = part.strip().partition("=")
        counts[key] = int(value or 0)
failed, errors, skipped = counts["failures"], counts["errors"], counts["skipped"]
passed = total - failed - errors - skipped
problems = re.findall(r"^(FAIL|ERROR): (\S+) \((\S+)\)", log, re.M)

data = json.loads((folder / "cobertura.json").read_text(encoding="utf-8"))
apps = defaultdict(lambda: [0, 0])
for path, info in data["files"].items():
    app = Path(path.replace("\\", "/")).parts[0]
    apps[app][0] += info["summary"]["num_statements"]
    apps[app][1] += info["summary"]["covered_lines"]

out = ["TABLA 12.3 — RESULTADOS DE PRUEBAS", "",
       f"Resultado general:   {final[-1][0] if final else 'SIN RESULTADO'}",
       f"Total de pruebas:    {total}", f"Aprobadas:           {passed}", f"Fallidas:            {failed}",
       f"Errores:             {errors}", f"Omitidas:            {skipped}",
       f"Duración:            {seconds:.1f} s", f"Cobertura total:     {data['totals']['percent_covered']:.1f} %",
       "", "Cobertura por aplicación", f"{'Aplicación':<18}{'Sentencias':>12}{'Cubiertas':>12}{'Cobertura':>12}"]
for app, (statements, covered) in sorted(apps.items()):
    out.append(f"{app:<18}{statements:>12}{covered:>12}{(100 * covered / statements if statements else 0):>11.1f}%")
if problems:
    out += ["", "PRUEBAS CON PROBLEMAS (registrar como incidencia, sección 13.3):"]
    out += [f"  {kind}: {name} ({where})" for kind, name, where in problems]
(folder / "resumen.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
