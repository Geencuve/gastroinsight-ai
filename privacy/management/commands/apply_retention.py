from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from ai_vision.models import DetectionEvent
from monitoring.models import Incident

from privacy.models import PrivacyPolicy


class Command(BaseCommand):
    help = (
        "Aplica las reglas de retención de eventos agregados e incidencias "
        "según la política de privacidad de cada local."
    )

    def handle(self, *args, **options):
        total_events_deleted = 0
        total_incidents_deleted = 0

        policies = PrivacyPolicy.objects.select_related("venue")

        for policy in policies:
            event_cutoff = timezone.now() - timedelta(
                days=policy.retain_aggregated_events_days
            )

            incident_cutoff = timezone.now() - timedelta(
                days=policy.retain_incidents_days
            )

            deleted_events, _ = DetectionEvent.objects.filter(
                session__camera__venue=policy.venue,
                detected_at__lt=event_cutoff,
            ).delete()

            deleted_incidents, _ = Incident.objects.filter(
                venue=policy.venue,
                occurred_at__lt=incident_cutoff,
            ).delete()

            total_events_deleted += deleted_events
            total_incidents_deleted += deleted_incidents

            self.stdout.write(
                (
                    f"{policy.venue.name}: "
                    f"{deleted_events} evento(s) y "
                    f"{deleted_incidents} incidencia(s) eliminados."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Retención aplicada. "
                    f"Eventos eliminados: {total_events_deleted}. "
                    f"Incidencias eliminadas: {total_incidents_deleted}."
                )
            )
        )