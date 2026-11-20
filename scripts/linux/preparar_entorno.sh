#!/usr/bin/env bash
# Prepara GastroInsight AI en Linux: entorno virtual, dependencias, modelos y base de datos.
# Uso (desde la carpeta del proyecto):  bash scripts/linux/preparar_entorno.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
echo "== Proyecto: $(pwd)"
command -v python3 >/dev/null || { echo "Falta python3: sudo apt install python3 python3-venv"; exit 1; }
if [ ! -d venv ]; then
  python3 -m venv venv || { echo "Instala venv: sudo apt install python3-venv"; exit 1; }
fi
venv/bin/python -m pip install --upgrade pip -q
venv/bin/pip install -r requirements.txt -q
venv/bin/pip install coverage -q
venv/bin/python scripts/download_models.py || echo "AVISO: no se pudieron descargar todos los modelos."
if [ ! -f ai_vision/ml_models/mesas_personas_yolo26s.onnx ]; then
  echo "AVISO: falta ai_vision/ml_models/mesas_personas_yolo26s.onnx (modelo YOLO del equipo). Cópialo ahí para E26."
fi
venv/bin/python manage.py migrate --noinput
mkdir -p evidencias
echo
echo "Listo. Para crear tu usuario administrador (si no tienes uno):"
echo "  venv/bin/python manage.py createsuperuser"
echo "Para iniciar la plataforma:"
echo "  venv/bin/python manage.py runserver"
