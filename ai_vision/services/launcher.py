"""Lanza el análisis visual como proceso en segundo plano desde la interfaz."""
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings

LOG_DIR = Path(os.environ.get("GI_LOG_DIR") or Path(settings.BASE_DIR) / "logs")


def _manage_command():
    """En el ejecutable de Windows los comandos se lanzan con: GastroInsightAI.exe manage <comando>."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "manage"]
    return [sys.executable, str(Path(settings.BASE_DIR) / "manage.py")]


def launch_analysis(session_id, preview=True, duration=0):
    """Inicia run_camera_analysis para la sesión. Retorna (pid, ruta_del_log)."""
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"analisis_{session_id}.log"
    args = [*_manage_command(), "run_camera_analysis", str(session_id)]
    if not preview:
        args.append("--no-preview")
    if duration:
        args += ["--duration", str(int(duration))]

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    kwargs = {"cwd": str(settings.BASE_DIR), "env": env, "stderr": subprocess.STDOUT}
    if sys.platform == "win32" and not preview:
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    with open(log_path, "a", encoding="utf-8") as log_file:
        process = subprocess.Popen(args, stdout=log_file, **kwargs)
    return process.pid, log_path


def launch_simulation(minutes=10):
    """Inicia simulate_live en segundo plano (datos sintéticos de las cámaras demo)."""
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / "simulacion_en_vivo.log"
    args = [*_manage_command(), "simulate_live", "--minutes", str(minutes)]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    kwargs = {"cwd": str(settings.BASE_DIR), "env": env, "stderr": subprocess.STDOUT}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    with open(log_path, "a", encoding="utf-8") as log_file:
        process = subprocess.Popen(args, stdout=log_file, **kwargs)
    return process.pid, log_path
