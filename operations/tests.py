from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from authentication.models import Profile
from operations.models import RestaurantTable, ServiceSession
from venues.models import Venue


class ServiceSessionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin_operations",
            password="AdminOperations123!",
            is_staff=True,
            is_superuser=True,
        )

        cls.viewer = User.objects.create_user(
            username="viewer_operations",
            password="ViewerOperations123!",
        )

        cls.venue = Venue.objects.create(
            name="Restaurante de prueba",
            is_active=True,
        )

        cls.table = RestaurantTable.objects.create(
            venue=cls.venue,
            code="M01",
            capacity=4,
            is_active=True,
        )

        admin_profile, _ = Profile.objects.get_or_create(
            user=cls.admin
        )
        admin_profile.role = Profile.Role.PLATFORM_ADMIN
        admin_profile.save()

        viewer_profile, _ = Profile.objects.get_or_create(
            user=cls.viewer
        )
        viewer_profile.role = Profile.Role.VIEWER
        viewer_profile.venues.add(cls.venue)

    def test_open_service_session_is_created(self):
        session = ServiceSession.objects.create(
            table=self.table,
            guests_count=3,
            created_by=self.admin,
        )

        self.assertEqual(
            session.status,
            ServiceSession.Status.OPEN,
        )

        self.assertEqual(session.table, self.table)
        self.assertEqual(session.guests_count, 3)

    def test_service_session_close_changes_status(self):
        session = ServiceSession.objects.create(
            table=self.table,
            guests_count=2,
            created_by=self.admin,
        )

        session.close(user=self.admin)
        session.refresh_from_db()

        self.assertEqual(
            session.status,
            ServiceSession.Status.CLOSED,
        )

        self.assertIsNotNone(session.ended_at)
        self.assertEqual(session.closed_by, self.admin)

    def test_viewer_cannot_open_service_session(self):
        self.client.force_login(self.viewer)

        response = self.client.get(
            reverse("operations:session_create")
        )

        self.assertEqual(response.status_code, 403)