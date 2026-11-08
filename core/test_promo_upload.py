import io
import tempfile
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from menus.models import Dish, Menu
from venues.models import Venue

MEDIA = tempfile.mkdtemp()


def png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 80, 40)).save(buffer, "PNG")
    return buffer.getvalue()


@override_settings(MEDIA_ROOT=MEDIA)
class PromoUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("jefa", password="Test12345!", is_superuser=True, is_staff=True)
        venue = Venue.objects.create(name="Local")
        self.dish = Dish.objects.create(menu=Menu.objects.create(venue=venue, name="Carta"), name="Lomo", category="Fondo", price=Decimal("9990"))
        self.client.force_login(self.user)

    def _upload(self, content, name="foto.png", kind="image/png"):
        return self.client.post("/promociones/subir/", {"query": f"plato={self.dish.id}", "foto": SimpleUploadedFile(name, content, kind)})

    def test_subir_imagen_valida_y_usarla_en_la_pieza(self):
        response = self._upload(png_bytes())
        self.assertEqual(response.status_code, 302)
        self.assertIn("fuente=subida", response.url)
        name = response.url.split("foto=")[1].split("&")[0]
        image = self.client.get(f"/promociones/imagen/?plato={self.dish.id}&fuente=subida&foto={name}")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image["Content-Type"], "image/jpeg")

    def test_rechaza_archivos_que_no_son_imagen(self):
        response = self._upload(b"esto no es una imagen", name="falsa.png")
        self.assertNotIn("foto=", response.url)

    def test_no_permite_usar_imagenes_de_otro_usuario(self):
        from core.promo_uploads import path_for

        name = self._upload(png_bytes()).url.split("foto=")[1].split("&")[0]
        other = User.objects.create_user("otro", password="Test12345!")
        self.assertIsNone(path_for(other, name))
        self.assertIsNone(path_for(self.user, "../../etc/passwd"))

    def test_generador_muestra_las_fuentes_de_imagen(self):
        response = self.client.get(f"/promociones/?plato={self.dish.id}")
        self.assertContains(response, "Imagen de la promoción")
        self.assertContains(response, "Subir imagen")
