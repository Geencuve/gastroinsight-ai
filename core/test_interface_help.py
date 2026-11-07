from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile


class InterfaceHelpTests(TestCase):
    def test_ayuda_por_pagina_cubre_las_pantallas_principales(self):
        script = Path("static/js/guide.js").read_text(encoding="utf-8-sig")
        self.assertIn("PAGE_HELP", script)
        for path in ("/garzon/", "/sala/", "/cocina/", "/caja/", "/vision/", "/gestion/", "/supervisor/", "/reports/explorar/"):
            self.assertIn(f'"{path}"', script)

    def test_estilos_responsive_presentes(self):
        styles = Path("static/css/theme.css").read_text(encoding="utf-8-sig")
        self.assertIn("H6 · Contenido centrado, responsive", styles)
        self.assertIn("@media (max-width: 760px)", styles)

    def test_pagina_carga_la_version_nueva_de_las_ayudas(self):
        user = User.objects.create_user("jefa", password="Test12345!", is_superuser=True, is_staff=True)
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()
        self.client.force_login(user)
        self.assertRegex(self.client.get("/").content.decode(), r"js/guide\.js\?v=\d+")
