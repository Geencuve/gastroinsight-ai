"""
Generador de piezas promocionales para redes sociales.

Compone la foto del plato con el titular, la oferta y el precio. Todo se genera
en el servidor con Pillow: no se envían datos a servicios externos.
"""
import os
from io import BytesIO

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

from menus.management.commands.generate_dish_images import load_font

ACCENT = (34, 211, 238)
ACCENT_2 = (139, 92, 246)
BG = (5, 7, 11)
BOLD_FONTS = ["segoeuib.ttf", "C:/Windows/Fonts/segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]
REGULAR_FONTS = ["segoeui.ttf", "C:/Windows/Fonts/segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"]


def _font(size, bold=False):
    font = load_font(BOLD_FONTS if bold else REGULAR_FONTS, size)
    return font or ImageFont.load_default(size=size)


def _wrap(draw, text, font, max_width):
    lines, line = [], ""
    for word in (text or "").split():
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _background(size, image_path):
    width, height = size
    if image_path and os.path.exists(image_path):
        with Image.open(image_path) as source:
            canvas = ImageOps.fit(source.convert("RGB"), size, method=Image.LANCZOS)
    else:
        canvas = Image.new("RGB", size)
        draw = ImageDraw.Draw(canvas)
        top, bottom = (40, 20, 90), (8, 40, 60)
        for y in range(height):
            t = y / (height - 1)
            draw.line([(0, y), (width, y)], fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))
    # Oscurece la parte inferior (texto) y un poco la superior (marca)
    gradient = Image.linear_gradient("L").resize(size)
    bottom_mask = gradient.point(lambda v: int(max(0, v - 80) * 240 / 175))
    top_mask = gradient.transpose(Image.FLIP_TOP_BOTTOM).point(lambda v: int(max(0, v - 190) * 170 / 65))
    canvas.paste(BG, (0, 0, width, height), ImageChops.lighter(bottom_mask, top_mask))
    return canvas


def render_promo(*, headline, title, offer="", price="", old_price="", venue_name="", image_path=None, story=False):
    width, height = (1080, 1920) if story else (1080, 1080)
    margin = 72
    canvas = _background((width, height), image_path)
    draw = ImageDraw.Draw(canvas)

    # Marca del local y titular
    draw.text((margin, margin), (venue_name or "").upper(), font=_font(30, True), fill=(255, 255, 255))
    draw.rectangle((margin, margin + 48, margin + 90, margin + 54), fill=ACCENT)
    head_font = _font(34, True)
    head_width = draw.textlength(headline, font=head_font)
    pill_top = margin + 84
    draw.rounded_rectangle((margin, pill_top, margin + head_width + 44, pill_top + 62), radius=31, fill=ACCENT)
    draw.text((margin + 22, pill_top + 31), headline, font=head_font, fill=BG, anchor="lm")

    # Bloque inferior: título, oferta, precio y pie
    max_width = width - 2 * margin
    title_font = _font(104 if story else 86, True)
    offer_font = _font(44 if story else 40)
    title_lines = _wrap(draw, title, title_font, max_width)[:3]
    offer_lines = _wrap(draw, offer, offer_font, max_width)[:2]

    footer_y = height - margin + 10
    draw.text((margin, footer_y), "Imagen generada con GastroInsight AI", font=_font(24), fill=(160, 170, 190), anchor="ls")

    block_bottom = footer_y - 60
    if price:
        price_font = _font(56, True)
        chip_height = 96
        chip_top = footer_y - 50 - chip_height
        price_width = draw.textlength(price, font=price_font)
        draw.rounded_rectangle((margin, chip_top, margin + price_width + 56, chip_top + chip_height), radius=24, fill=ACCENT_2)
        draw.text((margin + 28, chip_top + chip_height / 2), price, font=price_font, fill=(255, 255, 255), anchor="lm")
        if old_price:
            old_font = _font(34)
            x = margin + price_width + 80
            middle = chip_top + chip_height / 2
            draw.text((x, middle), old_price, font=old_font, fill=(175, 182, 198), anchor="lm")
            draw.line((x, middle, x + draw.textlength(old_price, font=old_font), middle), fill=(175, 182, 198), width=3)
        block_bottom = chip_top - 36

    offer_line_height = 54 if story else 50
    title_line_height = 118 if story else 98
    offer_top = block_bottom - len(offer_lines) * offer_line_height
    for index, line in enumerate(offer_lines):
        draw.text((margin, offer_top + index * offer_line_height), line, font=offer_font, fill=(226, 232, 240))
    title_top = offer_top - 24 - len(title_lines) * title_line_height
    for index, line in enumerate(title_lines):
        draw.text((margin, title_top + index * title_line_height), line, font=title_font, fill=(255, 255, 255))

    output = BytesIO()
    canvas.save(output, "JPEG", quality=90)
    return output.getvalue()


def build_caption(headline, title, offer, price, venue_name):
    text = f"✨ {headline.capitalize()}: {title}."
    if offer:
        text += f" {offer}."
    if price:
        text += f" Solo {price}."
    tag = "".join(ch for ch in (venue_name or "").title() if ch.isalnum())
    text += f"\n📍 Te esperamos en {venue_name}.\n#restaurante #gastronomia #santiago #chile"
    if tag:
        text += f" #{tag}"
    return text
