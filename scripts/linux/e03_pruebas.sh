#!/usr/bin/env bash
# E03: ejecuta todas las pruebas automatizadas con cobertura (versión Linux de ejecutar_pruebas.ps1).
# Uso: bash scripts/linux/e03_pruebas.sh
set -uo pipefail
cd "$(dirname "$0")/../.."
SALIDA="evidencias/E03"
mkdir -p "$SALIDA"
export PYTHONIOENCODING=utf-8
echo "Ejecutando todas las pruebas con cobertura (puede tardar varios minutos)..."
venv/bin/coverage run manage.py test --verbosity 2 > "$SALIDA/pruebas.log" 2>&1
CODIGO=$?
venv/bin/coverage report > "$SALIDA/cobertura.txt"
venv/bin/coverage html -d "$SALIDA/cobertura_html" -q
venv/bin/coverage json -o "$SALIDA/cobertura.json" -q
venv/bin/python scripts/resumen_pruebas.py "$SALIDA"
{ echo "Fecha: $(date '+%Y-%m-%d %H:%M')"; uname -a; lscpu | grep -E 'Model name|^CPU\(s\)'; free -h | head -2; } > "$SALIDA/equipo.txt"
if [ $CODIGO -ne 0 ]; then echo; echo "HAY PRUEBAS FALLIDAS: revisa $SALIDA/pruebas.log"; exit 1; fi
echo; echo "Todas las pruebas aprobadas. Evidencias en $SALIDA"
