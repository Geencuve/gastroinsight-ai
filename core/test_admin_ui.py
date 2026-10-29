from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile


class AdminAndUserMenuTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("gerente", password="Test12345!", is_staff=True, is_superuser=True,
                                             first_name="Ana")
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.client.force_login(self.user)

    def test_admin_con_estetica_de_gastroinsight(self):
        response = self.client.get("/admin/")
        self.assertContains(response, "css/admin_theme.css")
        self.assertContains(response, "Volver a GastroInsight")
        self.assertContains(response, "Panel de administración")

    def test_menu_de_usuario_con_cerrar_sesion(self):
        response = self.client.get("/")
        self.assertContains(response, "user-menu")
        self.assertContains(response, "Configuración de cuenta")
        self.assertContains(response, "Cerrar sesión")
