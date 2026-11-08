"""
GastroInsight AI para Windows: abre la aplicación en una ventana nativa (sin navegador).

- Los datos del local quedan en %LOCALAPPDATA%\\GastroInsightAI (base, fotos y registros).
- `GastroInsightAI.exe manage <comando>` ejecuta comandos de Django (lo usa el análisis de cámara).
- `GastroInsightAI.exe --red` abre el modo «red del local»: los celulares del personal se conectan
  por WiFi a http://<IP de este equipo>:8000 (Windows pedirá permitir el acceso en el firewall).
"""
import os
import secrets
import socket
import sys
import threading
import time
from pathlib import Path

APP_NAME = "GastroInsight AI"
LAN_PORT = 8000


def bundle_dir():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def data_dir():
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "GastroInsightAI"
    for folder in (base, base / "media", base / "logs"):
        folder.mkdir(parents=True, exist_ok=True)
    return base


def lan_ip():
    """IP de este equipo en la red local (no envía datos: solo consulta la ruta de salida)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def configure_environment(lan=False):
    data = data_dir()
    if getattr(sys, "frozen", False) and sys.stdout is None:
        log = open(data / "logs" / "aplicacion.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log
    secret_file = data / "secret.key"
    if not secret_file.exists():
        secret_file.write_text(secrets.token_urlsafe(50), encoding="utf-8")
    hosts = ["127.0.0.1", "localhost"]
    if lan:
        hosts += [lan_ip(), socket.gethostname()]
    os.environ.update({
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "SECRET_KEY": secret_file.read_text(encoding="utf-8").strip(),
        "DEBUG": "False",
        "ALLOWED_HOSTS": ",".join(dict.fromkeys(hosts)),
        "DB_ENGINE": "sqlite",
        "SQLITE_PATH": str(data / "gastroinsight.sqlite3"),
        "MEDIA_ROOT": str(data / "media"),
        "GI_LOG_DIR": str(data / "logs"),
        "SERVE_MEDIA": "True",
        "SERVE_STATIC": "True",
        "DESKTOP_MODE": "True",
        "GI_RED_LOCAL": "1" if lan else "0",
        "PYTHONIOENCODING": "utf-8",
    })
    root = str(bundle_dir())
    if root not in sys.path:
        sys.path.insert(0, root)
    os.chdir(root)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def port_available(port):
    with socket.socket() as sock:
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def wait_for(port, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return True
        except OSError:
            time.sleep(0.2)
    return False


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "manage":
        configure_environment()
        from django.core.management import execute_from_command_line

        execute_from_command_line(["manage.py", *sys.argv[2:]])
        return

    lan = "--red" in sys.argv[1:]
    configure_environment(lan)
    import django

    django.setup()
    from django.core.management import call_command

    call_command("migrate", interactive=False, verbosity=0)

    from waitress import serve

    from config.wsgi import application

    if lan:
        host, port = "0.0.0.0", (LAN_PORT if port_available(LAN_PORT) else free_port())
        address = lan_ip()
    else:
        host, port, address = "127.0.0.1", free_port(), "127.0.0.1"
    threading.Thread(
        target=serve, args=(application,),
        kwargs={"host": host, "port": port, "threads": 8, "_quiet": True}, daemon=True,
    ).start()
    wait_for(port)

    import webview

    title = APP_NAME + (f" · red del local: http://{address}:{port}" if lan else "")
    webview.settings["ALLOW_DOWNLOADS"] = True
    # En red local se abre con la IP para que los QR del personal lleven la dirección correcta
    webview.create_window(title, f"http://{address}:{port}/", width=1400, height=880, min_size=(1100, 700))
    webview.start()


if __name__ == "__main__":
    main()