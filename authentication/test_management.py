from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from ai_vision.models import AnalysisSession, DetectionEvent
from authentication.models import Profile
from cameras.models import Camera
from operations.models import RestaurantTable, ServiceSession
from venues.models import Venue


class ManagementTests(TestCase):
    def setUp(self):
        cache.clear()
        self.venue = Venue.objects.create(name="Local de prueba")

    def _user(self, name, role, zones=""):
        user = User.objects.create_user(name, password="Clave#Segura2026", first_name=name.title())
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.role, profile.zones = role, zones
        profile.save()
        profile.venues.add(self.venue)
        return user

    def test_acceso_de_gestion_rechaza_al_garzon_y_admite_al_administrador(self):
        self._user("garzon", Profile.Role.WAITER)
        response = self.client.post("/gestion/acceso/", {"username": "garzon", "password": "Clave#Segura2026"})
        self.assertContains(response, "Usa el acceso del personal")
        self.assertNotIn("_auth_user_id", self.client.session)
        self._user("duena", Profile.Role.VENUE_ADMIN)
        response = self.client.post("/gestion/acceso/", {"username": "duena", "password": "Clave#Segura2026"})
        self.assertRedirects(response, "/gestion/", fetch_redirect_response=False)

    def test_crear_personal_con_rol_local_y_zonas(self):
        self.client.force_login(self._user("supervisora", Profile.Role.SUPERVISOR))
        self.assertContains(self.client.get("/gestion/"), "Agregar persona")
        self.client.post("/gestion/personal/nuevo/", {
            "first_name": "Pedro", "username": "pedro", "password": "Garzon#Terraza2026", "role": "waiter",
            "venues": [self.venue.id], "zones": "Terraza",
        })
        pedro = User.objects.get(username="pedro")
        self.assertEqual(pedro.profile.role, "waiter")
        self.assertEqual(list(pedro.profile.venues.all()), [self.venue])
        self.assertEqual(pedro.profile.zones, "Terraza")

    def test_supervisor_no_puede_crear_administradores(self):
        self.client.force_login(self._user("supervisor", Profile.Role.SUPERVISOR))
        self.client.post("/gestion/personal/nuevo/", {
            "first_name": "Ana", "username": "ana", "password": "Admin#Local2026", "role": "venue_admin",
            "venues": [self.venue.id],
        })
        self.assertFalse(User.objects.filter(username="ana").exists())

    def test_el_garzon_solo_recibe_alertas_de_su_zona(self):
        salon = RestaurantTable.objects.create(venue=self.venue, code="S1", capacity=4, zone_name="Salón")
        session = ServiceSession.objects.create(table=salon, guests_count=2)
        camera = Camera.objects.create(venue=self.venue, name="Cam S1", source="demo",
                                       source_type=Camera.SourceType.DEMO, table=salon)
        analysis = AnalysisSession.objects.create(camera=camera, status="running")
        DetectionEvent.objects.create(session=analysis, faces_count=2, table=salon, service_session=session,
                                      occupancy=Decimal("2"), attention_seeking=Decimal("0.5"))
        self.client.force_login(self._user("terraza", Profile.Role.WAITER, zones="Terraza"))
        self.assertEqual(self.client.get("/notificaciones/").json()["count"], 0)
        cache.clear()
        self.client.force_login(self._user("salon", Profile.Role.WAITER, zones="Salón"))
        self.assertEqual(self.client.get("/notificaciones/").json()["count"], 1)
