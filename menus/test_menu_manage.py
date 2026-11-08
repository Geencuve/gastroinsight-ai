"""Carta y fotos: crear cartas, agregar y editar platos, y permisos."""
import io
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from authentication.models import Profile
from menus.models import Dish, Menu
from venues.models import Venue

TEMP_MEDIA = tempfile.mkdtemp()


def _image():
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 120, 40)).save(buffer, format="JPEG")
    return SimpleUploadedFile("plato.jpg", buffer.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class MenuManageTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.venue = Venue.objects.create(name="Local Carta")
        self.admin = self._user("jefa", Profile.Role.PLATFORM_ADMIN, superuser=True)
        self.menu = Menu.objects.create(venue=self.venue, name="Almuerzo")
        self.client.force_login(self.admin)

    def _user(self, name, role, superuser=False):
        user = User.objects.create_user(name, password="Clave#Segura2026", is_staff=superuser, is_superuser=superuser)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(self.venue)
        return user

    def test_listado_muestra_nueva_carta_y_crea_sin_duplicar(self):
        self.assertContains(self.client.get("/menus/"), 'id="dlg-menu"')
        response = self.client.post("/menus/nueva/", {"venue": self.venue.id, "name": "Bebidas"})
        menu = Menu.objects.get(name="Bebidas")
        self.assertRedirects(response, f"/menus/{menu.id}/", fetch_redirect_response=False)
        self.client.post("/menus/nueva/", {"venue": self.venue.id, "name": "bebidas"})
        self.assertEqual(Menu.objects.filter(venue=self.venue, name__iexact="bebidas").count(), 1)

    def test_agregar_plato_con_foto_y_editarlo(self):
        self.client.post(f"/menus/{self.menu.id}/platos/nuevo/", {
            "name": "Cazuela", "category": "Fondo", "price": "8990", "is_available": "on", "image": _image()})
        dish = Dish.objects.get(menu=self.menu, name="Cazuela")
        self.assertTrue(dish.image)
        self.client.post(f"/menus/{self.menu.id}/platos/{dish.id}/editar/", {
            "name": "Cazuela de vacuno", "category": "Fondo", "price": "9990"})
        dish.refresh_from_db()
        self.assertEqual((dish.name, int(dish.price), dish.is_available), ("Cazuela de vacuno", 9990, False))
        self.assertTrue(dish.image)
        self.assertContains(self.client.get(f"/menus/{self.menu.id}/"), "No disponible")
        self.assertNotContains(self.client.get(f"/menus/carta/{self.venue.id}/"), "Cazuela de vacuno")

    def test_plato_repetido_no_se_crea(self):
        Dish.objects.create(menu=self.menu, name="Pebre", price=0)
        self.client.post(f"/menus/{self.menu.id}/platos/nuevo/", {"name": "pebre", "price": "500"})
        self.assertEqual(Dish.objects.filter(menu=self.menu, name__iexact="pebre").count(), 1)

    def test_garzon_no_puede_crear_platos(self):
        self.client.force_login(self._user("garzon", Profile.Role.WAITER))
        response = self.client.post(f"/menus/{self.menu.id}/platos/nuevo/", {"name": "X", "price": "1"})
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(self.client.get(f"/menus/{self.menu.id}/"), 'id="dlg-dish"')