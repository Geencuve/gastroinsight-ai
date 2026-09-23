from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from authentication.models import Profile
from monitoring.models import AuditLog
from monitoring.services.audit import log_action
from venues.models import Venue


class AuditLogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="admin_test",
            password="AdminTest123!",
            is_staff=True,
            is_superuser=True,
        )

        cls.operator = User.objects.create_user(
            username="operator_test",
            password="OperatorTest123!",
        )

        cls.venue = Venue.objects.create(
            name="Local de prueba",
            is_active=True,
        )

        admin_profile, _ = Profile.objects.get_or_create(
            user=cls.admin
        )
        admin_profile.role = Profile.Role.PLATFORM_ADMIN
        admin_profile.save()

        operator_profile, _ = Profile.objects.get_or_create(
            user=cls.operator
        )
        operator_profile.role = Profile.Role.OPERATOR
        operator_profile.venues.add(cls.venue)

    def test_platform_admin_can_access_audit_log(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("monitoring:audit_log_list")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bitácora de auditoría")

    def test_operator_cannot_access_audit_log(self):
        self.client.force_login(self.operator)

        response = self.client.get(
            reverse("monitoring:audit_log_list")
        )

        self.assertEqual(response.status_code, 403)

    def test_log_action_creates_audit_record(self):
        self.client.force_login(self.admin)

        response = self.client.get("/")

        log_action(
            response.wsgi_request,
            action=AuditLog.Action.VIEW,
            module="testing",
            venue=self.venue,
            object_type="TestObject",
            object_id="1",
            description="Registro creado durante prueba automatizada.",
        )

        log = AuditLog.objects.get(module="testing")

        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.venue, self.venue)
        self.assertEqual(log.action, AuditLog.Action.VIEW)
        self.assertEqual(log.object_type, "TestObject")
        self.assertEqual(log.object_id, "1")