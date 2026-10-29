from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile
from venues.models import Venue


class ProfilePageTests(TestCase):
    def setUp(self):
        self.venue = Venue.objects.create(name="Local de prueba")
        self.user = User.objects.create_user("mesero", password="Test12345!", first_name="Luis", email="luis@local.cl")
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.OPERATOR
        profile.save()
        profile.venues.add(self.venue)
        User.objects.create_user("otro", password="Test12345!", email="ocupado@local.cl")
        self.client.force_login(self.user)

    def test_perfil_muestra_secciones_y_cierre_de_sesion(self):
        response = self.client.get("/auth/profile/")
        for text in ("Mis locales y permisos", "Configuración de cuenta", "Seguridad", "Preferencias",
                     "Mi actividad reciente", "Cerrar sesión", "Local de prueba", "Operador"):
            self.assertContains(response, text)

    def test_permisos_segun_rol(self):
        response = self.client.get("/auth/profile/")
        capabilities = {c["label"]: c["allowed"] for c in response.context["capabilities"]}
        self.assertTrue(capabilities["Operar mesas, pedidos, pagos y evaluaciones"])
        self.assertFalse(capabilities["Ver auditoría y administrar la plataforma"])

    def test_actualizar_datos_de_cuenta(self):
        response = self.client.post("/auth/profile/", {
            "first_name": "Luis", "last_name": "Pérez", "email": "luis.perez@local.cl", "phone": "+56 9 1111 2222",
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, "Pérez")
        self.assertEqual(self.user.profile.phone, "+56 9 1111 2222")

    def test_correo_duplicado_es_rechazado(self):
        response = self.client.post("/auth/profile/", {
            "first_name": "Luis", "last_name": "", "email": "ocupado@local.cl", "phone": "",
        })
        self.assertContains(response, "ya está registrado en otra cuenta")
