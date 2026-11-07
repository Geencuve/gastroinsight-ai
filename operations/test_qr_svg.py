from django.contrib.auth.models import User
from django.test import TestCase

from authentication.models import Profile
from venues.models import Venue


class QrScalableTests(TestCase):
    def test_qr_de_vinculacion_es_escalable(self):
        user = User.objects.create_user("garzon", password="Test12345!")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role = Profile.Role.WAITER
        profile.save()
        profile.venues.add(Venue.objects.create(name="Local"))
        self.client.force_login(user)
        html = self.client.get("/garzon/conectar/").content.decode()
        svg = html[html.find("<svg"):html.find(">", html.find("<svg"))]
        self.assertIn("viewBox", svg)
        self.assertNotIn('width="', svg)
