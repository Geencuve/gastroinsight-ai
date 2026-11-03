from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

size = 512
image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
gradient = Image.new("RGBA", (size, size))
draw = ImageDraw.Draw(gradient)
for i in range(size):
    t = i / (size - 1)
    draw.line([(0, i), (size, i)], fill=(int(34 + (139 - 34) * t), int(211 + (92 - 211) * t), int(238 + (246 - 238) * t), 255))
mask = Image.new("L", (size, size), 0)
ImageDraw.Draw(mask).ellipse((24, 24, size - 24, size - 24), fill=255)
image.paste(gradient, (0, 0), mask)
shine = Image.new("RGBA", (size, size), (0, 0, 0, 0))
ImageDraw.Draw(shine).ellipse((120, 90, 300, 250), fill=(255, 255, 255, 120))
image = Image.alpha_composite(image, shine.filter(ImageFilter.GaussianBlur(28)))
image.save(Path(__file__).with_name("icon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("Icono generado: desktop/icon.ico")
