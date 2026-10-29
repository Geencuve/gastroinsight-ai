from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile


class GuideTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("nuevo", password="Test12345!", is_superuser=True, is_staff=True)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.user = user
        self.client.force_login(user)

    def test_base_incluye_leyendas_y_tour(self):
        response = self.client.get("/")
        self.assertContains(response, "js/guide.js")
        self.assertContains(response, f'data-user-id="{self.user.pk}"')
        self.assertContains(response, "Ver tour guiado")

    def test_preferencias_de_leyendas_en_perfil(self):
        response = self.client.get("/auth/profile/")
        self.assertContains(response, "Leyendas de ayuda")
        self.assertContains(response, "data-start-tour")
