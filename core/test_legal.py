from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from authentication.models import Profile
from core.legal import LEGAL_VERSION
from core.models import LegalAcceptance


class LegalPagesTests(TestCase):
    def test_paginas_legales_publicas(self):
        for url, text in (("/legal/acerca/", "Gustavo Contreras"), ("/legal/terminos/", "Usos prohibidos"),
                          ("/legal/privacidad/", "Derechos del titular"), ("/legal/uso-educativo/", "fines educativos"),
                          ("/legal/contacto/", "Teresa Jesús Tapia Soto")):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertContains(response, text)

    def test_pie_de_pagina_con_enlaces_legales(self):
        response = self.client.get("/")
        self.assertContains(response, "Términos y condiciones")
        self.assertContains(response, "/legal/privacidad/")


@override_settings(LEGAL_ACCEPTANCE_REQUIRED=True)
class LegalAcceptanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("estudiante", password="Test12345!", first_name="Ana")
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.role = Profile.Role.OPERATOR
        profile.save()
        self.client.force_login(self.user)

    def test_exige_toma_de_conocimiento(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/legal/toma-de-conocimiento/?next=%2F", fetch_redirect_response=False)

    def test_aceptar_registra_y_permite_continuar(self):
        response = self.client.post("/legal/toma-de-conocimiento/", {
            "educational": "on", "terms": "on", "responsible": "on", "full_name": "Ana Pérez", "next": "/",
        })
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        acceptance = LegalAcceptance.objects.get(user=self.user)
        self.assertEqual(acceptance.version, LEGAL_VERSION)
        self.assertEqual(acceptance.full_name, "Ana Pérez")
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_sin_marcar_declaraciones_no_se_registra(self):
        self.client.post("/legal/toma-de-conocimiento/", {"full_name": "Ana Pérez"})
        self.assertFalse(LegalAcceptance.objects.exists())
