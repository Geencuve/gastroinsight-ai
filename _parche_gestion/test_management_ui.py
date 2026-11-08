"""Centro de gestión v2: pestañas amigables, guía de roles e interruptores."""
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from authentication.models import Profile
from venues.models import Venue


class ManagementUiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.venue = Venue.objects.create(name="Local")
        self.admin = self._user("jefe", Profile.Role.VENUE_ADMIN)
        self.client.force_login(self.admin)

    def _user(self, name, role):
        user = User.objects.create_user(name, password="Clave#Segura2026", first_name=name.title())
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(self.venue)
        return user

    def test_centro_muestra_ventanas_guia_de_roles_y_reglas_de_alerta(self):
        response = self.client.get("/gestion/")
        for text in ("data-mgmt-v2", 'id="dlg-staff"', 'id="dlg-camera"', "¿Qué puede hacer cada rol?",
                     "Mesa impaciente", "Sistema de caja (POS)", "mgmt-switch-ui", "mgmt-role-guide"):
            self.assertContains(response, text)
        guide = response.context["role_guide"]
        waiter = next(r for r in guide if r["key"] == Profile.Role.WAITER)
        self.assertTrue(waiter["caps"])

    def test_editar_cuenta_usa_interruptor_de_cuenta_activa(self):
        waiter = self._user("garzon", Profile.Role.WAITER)
        response = self.client.get(f"/gestion/personal/{waiter.pk}/")
        self.assertContains(response, "mgmt-switch")
        self.assertContains(response, "Cuenta activa")

    def test_detectar_camaras_ofrece_dos_caminos_y_ejemplos_ip(self):
        response = self.client.get("/gestion/camaras/detectar/")
        self.assertContains(response, "Conectada a este equipo")
        self.assertContains(response, "Cámara de red (IP)")
        response = self.client.get("/gestion/camaras/detectar/?ip=1")
        self.assertContains(response, "data-url-example")
