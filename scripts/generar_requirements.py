"""
Genera requirements.lock (pip freeze completo) y un requirements.txt con solo los paquetes
que el código importa o que settings.py declara (INSTALLED_APPS, MIDDLEWARE).
Uso: python scripts/generar_requirements.py
"""
import ast
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {"venv", ".venv", "build", "dist", ".git", "evidencias", "staticfiles", "media", "desktop", "__pycache__", "node_modules"}


def read_source(path):
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return None, None


local = {p.name for p in ROOT.iterdir() if p.is_dir() and (p / "__init__.py").exists()} | {p.stem for p in ROOT.glob("*.py")}
names, not_utf8, unreadable = set(), [], []
for path in ROOT.rglob("*.py"):
    relative = path.relative_to(ROOT)
    if SKIP & set(relative.parts):
        continue
    source, encoding = read_source(path)
    if encoding != "utf-8-sig":
        not_utf8.append(f"{relative} ({encoding or 'desconocida'})")
    if source is None:
        continue
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as error:
        unreadable.append(f"{relative}: {error.msg} (línea {error.lineno})")
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])

settings, _ = read_source(ROOT / "config" / "settings.py")
names.update(m.split(".")[0] for m in re.findall(r"['\"]([a-z_][a-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)['\"]", settings))

mapping = metadata.packages_distributions()
packages = {}
for name in sorted(names - set(sys.stdlib_module_names) - local):
    for dist in mapping.get(name, []):
        packages[dist] = metadata.version(dist)

freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, check=True).stdout
(ROOT / "requirements.lock").write_text(freeze, encoding="utf-8")

old_file = ROOT / "requirements.txt"
old = set()
if old_file.exists():
    old_text, _ = read_source(old_file)
    for line in (old_text or "").splitlines():
        line = line.split("#")[0].strip()
        if line:
            old.add(re.split(r"[=<>~!\[; ]", line)[0].lower().replace("_", "-"))

lines = ["# GastroInsight AI: dependencias que usa el código (generado por scripts/generar_requirements.py)",
         "# Entorno completo y exacto: requirements.lock", ""]
lines += [f"{dist}=={version}" for dist, version in sorted(packages.items(), key=lambda i: i[0].lower())]
old_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

new = {d.lower().replace("_", "-") for d in packages}
report = ["Paquetes en el requirements.txt nuevo:"] + [f"  {d}=={v}" for d, v in sorted(packages.items())]
report += ["", "Eliminados (estaban en el anterior y el código no los usa):"] + [f"  {d}" for d in sorted(old - new)]
report += ["", "Agregados (el código los usa y no estaban declarados):"] + [f"  {d}" for d in sorted(new - old)]
if not_utf8:
    report += ["", "AVISO: archivos .py que no están en UTF-8:"] + [f"  {f}" for f in not_utf8]
if unreadable:
    report += ["", "AVISO: archivos .py con errores de sintaxis (no analizados):"] + [f"  {f}" for f in unreadable]
(ROOT / "evidencias" / "E02").mkdir(parents=True, exist_ok=True)
(ROOT / "evidencias" / "E02" / "requirements_cambios.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
print("\n".join(report))
