"""
Descubrimiento de cámaras: dispositivos locales (índices de video) y cámaras de red (rtsp/http/https).
Solo comprueba que respondan y su resolución; ningún fotograma se guarda ni se muestra.
"""
import platform
from urllib.parse import urlparse

import cv2

ALLOWED_SCHEMES = {"rtsp", "rtsps", "http", "https"}


def probe_local(max_index=6):
    backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
    found = []
    for index in range(max_index):
        capture = cv2.VideoCapture(index, backend)
        try:
            if not capture.isOpened():
                continue
            ok, frame = capture.read()
            width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            del frame
            found.append({"source": str(index), "label": f"Cámara local #{index}" + (" (integrada)" if index == 0 else ""),
                          "resolution": f"{width}×{height}" if width else "—", "working": bool(ok)})
        finally:
            capture.release()
    return found


def validate_url(url):
    parsed = urlparse((url or "").strip())
    if parsed.scheme.lower() not in ALLOWED_SCHEMES or not parsed.hostname:
        raise ValueError("Usa una dirección rtsp://, http:// o https:// de una cámara de red.")
    return url.strip()


def probe_url(url, timeout_ms=4000):
    url = validate_url(url)
    capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG,
                               [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms, cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms])
    try:
        if not capture.isOpened():
            return {"source": url, "working": False, "resolution": "—"}
        ok, frame = capture.read()
        width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        del frame
        return {"source": url, "working": bool(ok), "resolution": f"{width}×{height}" if width else "—"}
    finally:
        capture.release()
