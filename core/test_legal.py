from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from core.legal import LEGAL_VERSION
from core.models import LegalAcceptance


class LegalPagesTests(TestCase):
    def test_paginas_legales_de_producto(self):
        for url, text in (("/legal/acerca/", "Gustavo Contreras"), ("/legal/terminos/", "Usos prohibidos"),
                          ("/legal/privacidad/", "Derechos del titular"), ("/legal/licencia/", "AGPL-3.0"),
                          ("/legal/contacto/", "Teresa Jesús Tapia Soto")):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertContains(response, text)

    def test_licencia_ofrece_el_codigo_fuente(self):
        self.assertContains(self.client.get("/legal/licencia/"), "github.com/Geencuve/gastroinsight-ai")

    def test_pie_de_pagina_de_producto(self):
        response = self.client.get("/")
        self.assertContains(response, "Términos de servicio")
        self.assertContains(response, "Código abierto")
        self.assertNotContains(response, "uso educativo")


@override_settings(LEGAL_ACCEPTANCE_REQUIRED=True)
class LegalAcceptanceTests(TestCase):
    def setUp(self):
        from authentication.models import Profile

        self.user = User.objects.create_user("estudiante", password="Test12345!", first_name="Ana")
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.OPERATOR
        profile.save()
        self.client.force_login(self.user)

    def test_exige_aceptar_los_terminos(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/legal/toma-de-conocimiento/?next=%2F", fetch_redirect_response=False)

    def test_aceptar_registra_y_permite_continuar(self):
        response = self.client.post("/legal/toma-de-conocimiento/", {
            "terms": "on", "educational": "on", "responsible": "on", "full_name": "Ana Pérez", "next": "/",
        })
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertEqual(LegalAcceptance.objects.get(user=self.user).version, LEGAL_VERSION)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_sin_marcar_declaraciones_no_se_registra(self):
        self.client.post("/legal/toma-de-conocimiento/", {"full_name": "Ana Pérez"})
        self.assertFalse(LegalAcceptance.objects.exists())
