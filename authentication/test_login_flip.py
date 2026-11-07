from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile


class LoginFlipTests(TestCase):
    def test_una_pantalla_con_ambos_accesos(self):
        response = self.client.get("/auth/login/")
        self.assertContains(response, "login-flip")
        self.assertContains(response, 'action="/auth/login/"')
        self.assertContains(response, 'action="/gestion/acceso/"')
        self.assertContains(response, "Login admin")
        self.assertNotContains(response, 'class="login-flip is-flipped"')

    def test_acceso_de_gestion_abre_la_tarjeta_girada(self):
        response = self.client.get("/gestion/acceso/")
        self.assertContains(response, "login-flip is-flipped")

    def test_error_de_gestion_se_muestra_del_lado_de_gestion(self):
        user = User.objects.create_user("garzon", password="Clave#Segura2026")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.WAITER
        profile.save()
        response = self.client.post("/gestion/acceso/", {"username": "garzon", "password": "Clave#Segura2026"})
        self.assertContains(response, 'class="login-flip is-flipped"')
        self.assertContains(response, "Usa el acceso del personal")

    def test_encabezado_sin_ingresar_y_pie_legal(self):
        response = self.client.get("/legal/acerca/")
        self.assertNotContains(response, "nav-register")
        for text in ("Privacidad y tus datos", "Ley N° 19.628", "Ley N° 21.719", "Sin reconocimiento facial"):
            self.assertContains(response, text)
