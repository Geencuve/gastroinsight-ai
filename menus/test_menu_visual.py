import io
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from authentication.models import Profile
from menus.models import Dish, Menu
from venues.models import Venue

TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class MenuVisualTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user("chef", password="Test12345!", is_staff=True, is_superuser=True)
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.venue = Venue.objects.create(name="Local de prueba")
        self.menu = Menu.objects.create(venue=self.venue, name="Carta")
        self.dish = Dish.objects.create(menu=self.menu, name="Pastel de choclo", category="Fondo", price=9490)

    def test_carta_publica_sin_iniciar_sesion(self):
        response = self.client.get(f"/menus/carta/{self.venue.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pastel de choclo")
        self.assertContains(response, "$9.490")

    def test_detalle_permite_subir_foto_al_administrador(self):
        self.client.force_login(self.user)
        response = self.client.get(f"/menus/{self.menu.id}/")
        self.assertContains(response, "Subir foto")

    def test_subir_foto_valida(self):
        buffer = io.BytesIO()
        Image.new("RGB", (40, 30), (200, 100, 50)).save(buffer, "JPEG")
        upload = SimpleUploadedFile("foto.jpg", buffer.getvalue(), content_type="image/jpeg")
        self.client.force_login(self.user)
        response = self.client.post(f"/menus/{self.menu.id}/dishes/{self.dish.id}/image/", {"image": upload})
        self.assertEqual(response.status_code, 302)
        self.dish.refresh_from_db()
        self.assertTrue(self.dish.image)

    def test_generar_ilustraciones(self):
        call_command("generate_dish_images")
        self.dish.refresh_from_db()
        self.assertTrue(self.dish.image)
