"""
HUD de la ventana de análisis: rostros con su expresión, cajas de YOLO26 y un panel lateral de indicadores.
Se dibuja solo para la vista previa local; el fotograma se descarta igual que siempre (nada se guarda).
"""
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

PANEL_W = 330
BG = (11, 14, 21)
PANEL = (17, 21, 31)
TRACK = (40, 46, 62)
TEXT = (230, 233, 240)
MUTED = (138, 147, 167)
ACCENT = (34, 211, 238)
VIOLET = (167, 139, 250)
OK = (52, 211, 153)
WARN = (251, 191, 36)
BAD = (251, 113, 133)
EMOTIONS = {"neutral": "Neutral", "happy": "Alegría", "surprised": "Sorpresa", "sad": "Tristeza",
            "angry": "Enojo", "disgust": "Disgusto", "fear": "Miedo", "contempt": "Desprecio"}
_FONTS = {}
_STATE = {"scene": None}


def _font(size, bold=False):
    key = (size, bold)
    if key not in _FONTS:
        names = ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]
        font = None
        for name in names:
            for base in ("C:/Windows/Fonts/", "/usr/share/fonts/truetype/dejavu/", ""):
                try:
                    font = ImageFont.truetype(base + name, size)
                    break
                except OSError:
                    continue
            if font:
                break
        _FONTS[key] = font or ImageFont.load_default()
    return _FONTS[key]


def _ieo_color(value):
    if value is None:
        return MUTED
    return OK if value >= 65 else WARN if value >= 45 else BAD


def _pill(draw, x, y, text, color, filled=False):
    font = _font(13, bold=True)
    width = draw.textlength(text, font=font)
    draw.rounded_rectangle([x, y, x + width + 16, y + 22], radius=11,
                           fill=color + (235,) if filled else (5, 7, 11, 190), outline=color + (255,))
    draw.text((x + 8, y + 3), text, font=font, fill=(255, 255, 255) if filled else color)


def _corners(draw, x, y, w, h, color, size=14, width=3):
    for (cx, cy, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        draw.line([(cx, cy), (cx + dx * size, cy)], fill=color, width=width)
        draw.line([(cx, cy), (cx, cy + dy * size)], fill=color, width=width)


def _bar(draw, x, y, w, ratio, color, centered=False):
    draw.rounded_rectangle([x, y, x + w, y + 8], radius=4, fill=TRACK)
    ratio = max(0.0, min(1.0, ratio))
    if centered:
        mid = x + w / 2
        end = x + w * ratio
        draw.rounded_rectangle([min(mid, end), y, max(mid, end), y + 8], radius=4, fill=color)
        draw.line([(mid, y - 2), (mid, y + 10)], fill=MUTED, width=1)
    elif ratio > 0:
        draw.rounded_rectangle([x, y, x + max(8, w * ratio), y + 8], radius=4, fill=color)


def _row(draw, x, y, label, value, ratio=None, color=ACCENT, centered=False):
    draw.text((x, y), label, font=_font(13), fill=MUTED)
    value_font = _font(15, bold=True)
    draw.text((x + PANEL_W - 40 - draw.textlength(value, font=value_font), y - 2), value, font=value_font, fill=TEXT)
    if ratio is not None:
        _bar(draw, x, y + 22, PANEL_W - 40, ratio, color, centered)
    return y + (40 if ratio is not None else 26)


def render_hud(frame, result, info):
    """Compone el fotograma con el HUD. info: camera, table, events, frame, elapsed, summary."""
    from ai_vision.services.experience import experience_index

    if result.get("scene"):
        _STATE["scene"] = result["scene"]
    scene = _STATE["scene"] or {}
    summary = info.get("summary") or {}
    h, w = frame.shape[:2]
    height = max(h, 560)
    canvas = np.zeros((height, w + PANEL_W, 3), np.uint8)
    canvas[:, :] = BG[::-1]
    canvas[:h, :w] = frame
    image = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image, "RGBA")

    for box in scene.get("boxes") or []:
        cx, cy, bw, bh, kind = box[:5]
        x0, y0, x1, y1 = (cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h
        draw.rectangle([x0, y0, x1, y1], outline=(VIOLET if kind == "p" else MUTED) + (170,), width=1)

    for face in result.get("faces", []):
        b = face.get("box") or {}
        x, y, bw, bh = b.get("x", 0), b.get("y", 0), b.get("width", 0), b.get("height", 0)
        away = face.get("looking_away")
        color = WARN if away else ACCENT
        _corners(draw, x, y, bw, bh, color)
        label = EMOTIONS.get(face.get("emotion"), face.get("emotion") or "—")
        confidence = face.get("emotion_confidence")
        text = f"{label} {confidence:.0%}" if isinstance(confidence, (int, float)) else label
        if away:
            text += " · mira alrededor"
        _pill(draw, x, max(0, y - 28), text, color)

    _pill(draw, 12, 12, "● PROCESANDO EN MEMORIA · NO SE GRABA", BAD, filled=True)

    px = w
    draw.rectangle([px, 0, px + PANEL_W, height], fill=PANEL)
    draw.line([(px, 0), (px, height)], fill=TRACK, width=1)
    x = px + 20
    draw.text((x, 18), "GastroInsight AI", font=_font(20, bold=True), fill=ACCENT)
    draw.text((x, 46), "Análisis en vivo", font=_font(13), fill=MUTED)
    draw.text((x, 68), f"{info.get('camera', '')}", font=_font(14, bold=True), fill=TEXT)
    if info.get("table"):
        draw.text((x, 88), f"Mesa {info['table']}", font=_font(13), fill=MUTED)

    valence = summary.get("valence")
    attention = summary.get("attention_seeking")
    ieo = experience_index(valence, attention)
    draw.rounded_rectangle([x, 116, x + PANEL_W - 40, 196], radius=14, fill=(23, 28, 41))
    draw.text((x + 14, 126), "Índice de Experiencia Observable", font=_font(12), fill=MUTED)
    draw.text((x + 14, 144), f"{ieo:.0f}" if ieo is not None else "—", font=_font(38, bold=True), fill=_ieo_color(ieo))
    draw.text((x + 96, 164), "de 100", font=_font(12), fill=MUTED)

    elapsed = max(0.001, float(info.get("elapsed") or 0.001))
    fps = (info.get("frame") or 0) / elapsed
    latency = float(result.get("processing_time_ms") or 0)
    y = 216
    y = _row(draw, x, y, "FPS", f"{fps:.1f}", fps / 30, OK if fps >= 15 else WARN)
    y = _row(draw, x, y, "Latencia por fotograma", f"{latency:.0f} ms", latency / 200, OK if latency < 200 else BAD)
    y = _row(draw, x, y, "Rostros detectados", str(result.get("faces_count", 0)))
    persons = scene.get("persons")
    y = _row(draw, x, y, "Personas / mesas (YOLO26)",
             f"{persons} / {scene.get('tables', '—')}" if persons is not None else "—")
    if valence is not None:
        y = _row(draw, x, y, "IBE (balance de expresiones)", f"{valence:+.2f}", (valence + 1) / 2,
                 OK if valence >= 0 else BAD, centered=True)
    if attention is not None:
        y = _row(draw, x, y, "Búsqueda de atención", f"{attention:.0%}", attention, WARN if attention >= 0.3 else ACCENT)
    activity = summary.get("activity_level")
    if activity is not None:
        y = _row(draw, x, y, "Actividad", f"{activity:.0f}", activity / 100, VIOLET)

    minutes, seconds = divmod(int(elapsed), 60)
    draw.text((x, height - 52), f"Eventos guardados: {info.get('events', 0)} · Fotograma {info.get('frame', 0)} · "
                                f"{minutes:02d}:{seconds:02d}", font=_font(12), fill=MUTED)
    draw.text((x, height - 32), "Q: detener  ·  Fotogramas en memoria, nada se guarda", font=_font(12), fill=MUTED)
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
