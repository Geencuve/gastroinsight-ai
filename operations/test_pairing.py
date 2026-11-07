import time
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from authentication.models import Profile
from operations.services.pairing import make_token
from venues.models import Venue


class PairingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.venue = Venue.objects.create(name="Local de prueba")

    def _user(self, name, role):
        user = User.objects.create_user(name, password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = role
        profile.save()
        profile.venues.add(self.venue)
        return user

    def test_garzon_genera_su_codigo(self):
        self.client.force_login(self._user("garzon", Profile.Role.WAITER))
        response = self.client.get("/garzon/conectar/")
        self.assertContains(response, "Conecta tu celular")
        self.assertContains(response, "<svg")

    def test_codigo_inicia_sesion_una_sola_vez(self):
        waiter = self._user("garzona", Profile.Role.WAITER)
        url = reverse("waiter:pair_login", args=[make_token(waiter)])
        response = self.client.get(url)
        self.assertRedirects(response, "/garzon/", fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), waiter.pk)
        self.client.logout()
        response = self.client.get(url)
        self.assertContains(response, "ya se usó", status_code=400)

    def test_codigo_caduca_a_los_cinco_minutos(self):
        waiter = self._user("garzon2", Profile.Role.WAITER)
        url = reverse("waiter:pair_login", args=[make_token(waiter)])
        with mock.patch("django.core.signing.time.time", return_value=time.time() + 301):
            response = self.client.get(url)
        self.assertContains(response, "caducó", status_code=400)

    def test_cuentas_de_gestion_no_se_vinculan_por_qr(self):
        supervisor = self._user("sup", Profile.Role.SUPERVISOR)
        self.client.force_login(supervisor)
        self.assertEqual(self.client.get("/garzon/conectar/").status_code, 403)
        response = self.client.get(reverse("waiter:pair_login", args=[make_token(supervisor)]))
        self.assertEqual(response.status_code, 400)

    def test_supervisor_genera_qr_para_un_garzon(self):
        waiter = self._user("pedro", Profile.Role.WAITER)
        self.client.force_login(self._user("jefa", Profile.Role.SUPERVISOR))
        self.assertContains(self.client.get(f"/gestion/personal/{waiter.pk}/qr/"), "Conecta tu celular")
