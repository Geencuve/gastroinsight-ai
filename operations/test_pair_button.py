from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile
from venues.models import Venue


class PairButtonTests(TestCase):
    def _login(self, name, role):
        user = User.objects.create_user(name, password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(Venue.objects.get_or_create(name="Local")[0])
        self.client.force_login(user)

    def test_boton_conectar_celular_solo_para_cuentas_de_servicio(self):
        self._login("garzon", Profile.Role.WAITER)
        self.assertContains(self.client.get("/garzon/"), "Conectar celular")
        self._login("supervisora", Profile.Role.SUPERVISOR)
        self.assertNotContains(self.client.get("/garzon/"), "Conectar celular")
