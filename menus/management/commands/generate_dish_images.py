import io

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw, ImageFont

from menus.models import Dish

PALETTES = {
    "Entrada": ((14, 116, 144), (8, 30, 46)),
    "Fondo": ((109, 40, 217), (24, 16, 54)),
    "Postre": ((219, 39, 119), (60, 10, 33)),
    "Bebida": ((5, 150, 105), (5, 38, 30)),
}
DEFAULT_PALETTE = ((37, 99, 235), (12, 18, 38))
NAME_EMOJI = [
    ("salm", "🐟"), ("ceviche", "🐟"), ("risotto", "🍄"), ("tiramis", "🍰"), ("limonada", "🍋"),
    ("empanada", "🥟"), ("queso", "🧀"), ("lomo", "🥩"), ("choclo", "🌽"), ("pollo", "🍗"),
    ("leche asada", "🍮"), ("pisco", "🍸"), ("jugo", "🧃"), ("caf", "☕"),
]
CATEGORY_EMOJI = {"Entrada": "🥟", "Fondo": "🍽", "Postre": "🍰", "Bebida": "🍹"}


def load_font(candidates, size):
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return None


def render_dish(dish):
    width, height = 800, 600
    top, bottom = PALETTES.get(dish.category, DEFAULT_PALETTE)
    image = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / (height - 1)
        draw.line([(0, y), (width, y)], fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))

    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((190, 40, 610, 420), fill=(255, 255, 255, 26))
    image = Image.alpha_composite(image, glow)
    draw = ImageDraw.Draw(image)

    emoji = next((e for key, e in NAME_EMOJI if key in dish.name.lower()), CATEGORY_EMOJI.get(dish.category, "🍽"))
    emoji_font = load_font(["seguiemj.ttf", "C:/Windows/Fonts/seguiemj.ttf"], 170)
    bold = load_font(["segoeuib.ttf", "C:/Windows/Fonts/segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 46)
    regular = load_font(["segoeui.ttf", "C:/Windows/Fonts/segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], 26)
    drawn = False
    if emoji_font:
        try:
            draw.text((width / 2, 230), emoji, font=emoji_font, anchor="mm", embedded_color=True)
            drawn = True
        except Exception:
            drawn = False
    if not drawn and bold:
        big = load_font(["segoeuib.ttf", "C:/Windows/Fonts/segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"], 180)
        draw.text((width / 2, 230), dish.name[:1].upper(), font=big, anchor="mm", fill=(255, 255, 255))

    band = Image.new("RGBA", (width, 150), (0, 0, 0, 120))
    image.alpha_composite(band, (0, height - 150))
    draw = ImageDraw.Draw(image)
    name = dish.name if len(dish.name) <= 28 else dish.name[:27] + "…"
    price = "$" + f"{int(dish.price):,}".replace(",", ".")
    if bold and regular:
        draw.text((40, height - 122), name, font=bold, fill=(255, 255, 255))
        draw.text((40, height - 58), f"{dish.category or 'Plato'}  ·  {price}", font=regular, fill=(226, 232, 240))
    else:
        draw.text((40, height - 110), f"{name} - {price}", fill=(255, 255, 255))

    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=88)
    return buffer.getvalue()


class Command(BaseCommand):
    help = "Genera ilustraciones para los platos sin foto (o todas con --force)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Regenera también los platos que ya tienen foto.")

    def handle(self, *args, **options):
        created = 0
        for dish in Dish.objects.all():
            if dish.image and not options["force"]:
                continue
            dish.image.save(f"plato_{dish.id}.jpg", ContentFile(render_dish(dish)), save=True)
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Ilustraciones generadas: {created}"))
