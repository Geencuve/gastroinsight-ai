from django.contrib.auth.models import User
from django.test import TestCase

from privacy.models import PrivacyPolicy, ProcessingAuthorization
from venues.models import Venue


class PrivacyPolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="privacy_test",
            password="PrivacyTest123!",
        )

        cls.venue = Venue.objects.create(
            name="Local privacidad",
            is_active=True,
        )

    def test_processing_is_not_authorized_without_policy_enabled(self):
        policy = PrivacyPolicy.objects.create(
            venue=self.venue,
            purpose="Prueba de privacidad.",
            processing_enabled=False,
            store_original_images=False,
            updated_by=self.user,
        )

        ProcessingAuthorization.objects.create(
            privacy_policy=policy,
            source_description="Webcam de prueba",
            status=ProcessingAuthorization.Status.ACTIVE,
            accepted_by=self.user,
        )

        self.assertFalse(policy.is_processing_authorized)

    def test_processing_is_authorized_with_active_policy_and_authorization(self):
        policy = PrivacyPolicy.objects.create(
            venue=self.venue,
            purpose="Prueba de privacidad.",
            processing_enabled=True,
            store_original_images=False,
            updated_by=self.user,
        )

        ProcessingAuthorization.objects.create(
            privacy_policy=policy,
            source_description="Webcam de prueba",
            status=ProcessingAuthorization.Status.ACTIVE,
            accepted_by=self.user,
        )

        self.assertTrue(policy.is_processing_authorized)

    def test_processing_is_not_authorized_if_original_images_enabled(self):
        policy = PrivacyPolicy.objects.create(
            venue=self.venue,
            purpose="Prueba de privacidad.",
            processing_enabled=True,
            store_original_images=True,
            updated_by=self.user,
        )

        ProcessingAuthorization.objects.create(
            privacy_policy=policy,
            source_description="Webcam de prueba",
            status=ProcessingAuthorization.Status.ACTIVE,
            accepted_by=self.user,
        )

        self.assertFalse(policy.is_processing_authorized)