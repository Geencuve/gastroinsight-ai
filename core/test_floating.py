from django.contrib.auth.models import User
from django.test import TestCase


class FloatingWindowsTests(TestCase):
    def test_base_incluye_ventanas_flotantes_y_punto_de_venta(self):
        user = User.objects.create_user("jefa", password="Test12345!", is_superuser=True, is_staff=True)
        self.client.force_login(user)
        response = self.client.get("/legal/acerca/")
        self.assertContains(response, "js/float.js")
        self.assertContains(response, "js/pos.js")
