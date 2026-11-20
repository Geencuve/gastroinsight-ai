#!/usr/bin/env bash
# E28 (y cierre de E03): regenera las evidencias de pruebas, cobertura y auditoría por rol
# con la versión congelada que se entrega.
# Uso (desde la carpeta del proyecto, con el código ya en la versión final):
#   bash scripts/linux/e28_regenerar_evidencias.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
SALIDA="evidencias/E28"
mkdir -p "$SALIDA"
export PYTHONIOENCODING=utf-8

if [ -n "$(git status --porcelain -- . ':!evidencias' ':!scripts/linux' 2>/dev/null)" ]; then
  echo "AVISO: hay cambios sin confirmar en el código. La versión congelada debe estar confirmada en Git."
  echo "       Confirma con: git add -A && git commit -m 'Versión congelada para el informe'  y vuelve a ejecutar."
  exit 1
fi
{ echo "Commit: $(git rev-parse HEAD)"; echo "Fecha del commit: $(git log -1 --format=%cd)";
  echo "Etiquetas: $(git tag --points-at HEAD | tr '\n' ' ')"; echo "Ejecución: $(date '+%Y-%m-%d %H:%M')"; } > "$SALIDA/commit.txt"
venv/bin/pip freeze > "$SALIDA/entorno.txt"
{ uname -a; lscpu | grep -E 'Model name|^CPU\(s\)'; free -h | head -2; venv/bin/python --version; } > "$SALIDA/equipo.txt"

echo "1/2 Pruebas con cobertura (varios minutos)..."
venv/bin/coverage run manage.py test --verbosity 2 > "$SALIDA/pruebas.log" 2>&1
CODIGO=$?
venv/bin/coverage report > "$SALIDA/cobertura.txt"
venv/bin/coverage json -o "$SALIDA/cobertura.json" -q
venv/bin/python scripts/resumen_pruebas.py "$SALIDA" > /dev/null

echo "2/2 Auditoría de pantallas por rol..."
venv/bin/python manage.py auditar_roles --salida "$SALIDA" > "$SALIDA/auditoria.log" 2>&1

echo
cat "$SALIDA/commit.txt"; echo
head -10 "$SALIDA/resumen.txt"
grep -E "Resultado|Pantallas" "$SALIDA/auditoria_roles.md" 2>/dev/null
echo
if [ $CODIGO -ne 0 ]; then echo "HAY PRUEBAS FALLIDAS: revisa $SALIDA/pruebas.log"; exit 1; fi
echo "Listo. Evidencias en $SALIDA. Comprime esa carpeta y pásamela para cerrar E03 y E28 en el informe."
