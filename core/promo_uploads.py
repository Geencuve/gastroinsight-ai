"""
Imágenes propias para las promociones. Se validan, se reprocesan (orientación, máx. 1600 px, JPG nuevo sin metadatos)
y se guardan con un nombre aleatorio en una carpeta por usuario. Se conservan las últimas 12.
"""
import re
import uuid
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageOps

MAX_BYTES = 6 * 1024 * 1024
MAX_PIXELS = 40_000_000
KEEP = 12
NAME = re.compile(r"^[0-9a-f]{32}$")


def _folder(user):
    folder = Path(settings.MEDIA_ROOT) / "promo_uploads" / str(user.pk)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_upload(user, upload):
    if upload.size > MAX_BYTES:
        raise ValueError("La imagen supera los 6 MB.")
    try:
        probe = Image.open(upload)
        probe.verify()
        upload.seek(0)
        image = Image.open(upload)
        if image.width * image.height > MAX_PIXELS:
            raise ValueError("La imagen es demasiado grande.")
        if (image.format or "").upper() not in {"JPEG", "PNG", "WEBP", "MPO"}:
            raise ValueError("Formato no permitido: usa JPG, PNG o WebP.")
        image = ImageOps.exif_transpose(image).convert("RGB")
    except ValueError:
        raise
    except Exception:
        raise ValueError("El archivo no es una imagen válida (usa JPG, PNG o WebP).")
    image.thumbnail((1600, 1600))
    name = uuid.uuid4().hex
    folder = _folder(user)
    image.save(folder / f"{name}.jpg", "JPEG", quality=88, optimize=True)
    files = sorted(folder.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[KEEP:]:
        old.unlink(missing_ok=True)
    return name


def path_for(user, name):
    if not name or not NAME.match(name):
        return None
    path = _folder(user) / f"{name}.jpg"
    return path if path.exists() else None


def recent(user, limit=6):
    files = sorted(_folder(user).glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    return [{"name": p.stem, "url": f"{settings.MEDIA_URL}promo_uploads/{user.pk}/{p.name}"} for p in files]
