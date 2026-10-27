from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile
from core.services.promo_images import build_caption, render_promo
from menus.models import Dish, Menu
from venues.models import Venue


class PromoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("marketing", password="Test12345!", is_staff=True, is_superuser=True)
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        venue = Venue.objects.create(name="Local de prueba")
        menu = Menu.objects.create(venue=venue, name="Carta")
        self.main = Dish.objects.create(menu=menu, name="Lomo vetado", category="Fondo", price=Decimal("15990"))
        self.drink = Dish.objects.create(menu=menu, name="Pisco sour", category="Bebida", price=Decimal("5490"))
        self.client.force_login(self.user)

    def test_render_genera_jpeg_cuadrado_e_historia(self):
        for story in (False, True):
            data = render_promo(headline="COMBO", title="Lomo + Pisco", offer="Ahorra", price="$19.290",
                                old_price="$21.480", venue_name="Local", story=story)
            self.assertTrue(data.startswith(b"\xff\xd8"))

    def test_generador_calcula_precio_de_combo(self):
        response = self.client.get(f"/promociones/?tipo=combo&plato={self.main.id}&plato2={self.drink.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["promo"]["old_price"], "$21.480")
        self.assertEqual(response.context["promo"]["price"], "$19.290")

    def test_imagen_y_descarga(self):
        response = self.client.get(f"/promociones/imagen/?tipo=estrella&plato={self.main.id}&descargar=1")
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertIn("attachment", response["Content-Disposition"])

    def test_texto_para_redes(self):
        caption = build_caption("PLATO ESTRELLA", "Lomo vetado", "El favorito", "$15.990", "Local de prueba")
        self.assertIn("Lomo vetado", caption)
        self.assertIn("#LocalDePrueba", caption)
