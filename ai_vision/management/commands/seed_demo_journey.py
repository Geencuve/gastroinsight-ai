"""Journeys completos de demostración (datos SINTÉTICOS).

Completa las atenciones de demostración con la entrega de platos y la solicitud de la cuenta, y genera
lecturas visuales en las 4 etapas del journey y en la caja al momento de pagar. Siempre por mesa.
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Avg
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from cameras.models import Camera
from operations.models import ServiceSession

TAG = "Datos sintéticos de demostración (journey)."
SALES_TAG = "Generado automáticamente para demo."
CAMERA_NOTE = "Cámara de demostración: genera datos SINTÉTICOS, no procesa video real."
BASE = {"llegada": 68, "espera": 57, "consumo": 79, "cuenta": 71}
ATTENTION = {"llegada": 0.18, "espera": 0.32, "consumo": 0.08, "cuenta": 0.22}


def _clamp(value, low, high):
    return max(low, min(high, value))


def demo_camera(venue, name, **flags):
    camera = Camera.objects.filter(venue=venue, name=name).first()
    if camera is None:
        slug = name.lower().replace(" ", "-")
        camera = Camera.objects.create(venue=venue, name=name, source_type=Camera.SourceType.DEMO,
                                       source=f"demo-{slug}", notes=CAMERA_NOTE, **flags)
    return camera


class Command(BaseCommand):
    help = "Genera journeys completos y lecturas en caja SINTÉTICOS sobre las ventas de demostración."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Borra y regenera las lecturas del journey demo.")
        parser.add_argument("--dias", type=int, default=14)
        parser.add_argument("--semilla", type=int, default=2026)

    def handle(self, *args, reset=False, dias=14, semilla=2026, **options):
        from ai_vision.services.checkout import checkout_at_payment
        from operations.services.journey import journey_stats, session_stages
        from sales.models import Order, OrderItem

        rng = random.Random(semilla)
        previous = AnalysisSession.objects.filter(error_message=TAG)
        if reset:
            count = previous.count()
            DetectionEvent.objects.filter(session__in=previous).delete()
            previous.delete()
            self.stdout.write(f"Reset: {count} sesiones de journey demo eliminadas.")
        elif previous.exists():
            self.stdout.write(self.style.WARNING("Ya existen journeys demo. Usa --reset para regenerarlos."))
            return

        evaluation = next((m for m in apps.get_models() if m.__name__ == "SatisfactionEvaluation"), None)
        has_bill = "bill_requested_at" in {f.name for f in ServiceSession._meta.fields}
        since = timezone.now() - timedelta(days=dias)
        sessions = (ServiceSession.objects.filter(notes=SALES_TAG, status=ServiceSession.Status.CLOSED, started_at__gte=since)
                    .select_related("table__venue").order_by("-started_at")[:200])
        self.pending, analyses, venues = [], {}, {}
        stats = {"atenciones": 0, "lecturas": 0, "caja": 0}

        with transaction.atomic():
            for session in sessions:
                order = Order.objects.filter(service_session=session, paid_at__isnull=False).order_by("-paid_at").first()
                if order is None or not order.confirmed_at or order.paid_at <= order.confirmed_at:
                    continue
                venue = session.table.venue
                venues[venue.pk] = venue
                if venue.pk not in analyses:
                    analyses[venue.pk] = (
                        self._analysis(demo_camera(venue, "Cámara demo journey", is_active=False)),
                        self._analysis(demo_camera(venue, "Cámara demo caja", is_checkout=True)),
                    )
                journey, checkout = analyses[venue.pk]

                # Completa la línea de tiempo: platos entregados y cuenta solicitada
                span = order.paid_at - order.confirmed_at
                delivered = order.confirmed_at + timedelta(minutes=rng.randint(12, 26))
                if delivered >= order.paid_at - timedelta(minutes=10):
                    delivered = order.confirmed_at + span / 3
                OrderItem.objects.filter(order=order, delivered_at__isnull=True).update(delivered_at=delivered, prep_status="delivered")
                if has_bill and not session.bill_requested_at:
                    bill = order.paid_at - timedelta(minutes=rng.randint(5, 9))
                    ServiceSession.objects.filter(pk=session.pk).update(bill_requested_at=bill)
                    session.bill_requested_at = bill

                rating = evaluation.objects.filter(service_session=session).aggregate(r=Avg("rating"))["r"] if evaluation else None
                mood = (float(rating) - 3.6) * 7 if rating else rng.gauss(0, 6)
                faces = session.guests_count or 2
                for key, start, stop in session_stages(session):
                    seconds = (stop - start).total_seconds()
                    n = int(_clamp(seconds // 180, 2, 8))
                    for i in range(n):
                        moment = start + timedelta(seconds=seconds * (i + 0.5) / n)
                        ieo = _clamp(BASE[key] + mood + rng.gauss(0, 5), 5, 98)
                        attention = _clamp(ATTENTION[key] + rng.gauss(0, 0.05), 0, 1)
                        self._event(journey, session.table, session, moment, ieo, attention, faces)
                        stats["lecturas"] += 1
                for seconds in (75, 40, 10):
                    ieo = _clamp(BASE["cuenta"] + mood + rng.gauss(0, 4), 5, 98)
                    self._event(checkout, None, session, order.paid_at - timedelta(seconds=seconds), ieo, 0.15, min(faces, 2))
                    stats["caja"] += 1
                stats["atenciones"] += 1

            for pk, moment in self.pending:
                DetectionEvent.objects.filter(pk=pk).update(detected_at=moment)

        self.stdout.write(self.style.SUCCESS("Journeys SINTÉTICOS de demostración creados."))
        self.stdout.write(f" - Atenciones completadas: {stats['atenciones']}")
        self.stdout.write(f" - Lecturas por etapa: {stats['lecturas']} · lecturas en caja: {stats['caja']}")
        for item in journey_stats(list(venues.values()), days=dias):
            value = f"IEO {item['ieo']:.0f} ({item['n']} atenciones)" if item["ieo"] is not None else "sin lecturas"
            self.stdout.write(f"   · {item['label']}: {value}")
        last = Order.objects.filter(service_session__notes=SALES_TAG, paid_at__isnull=False).order_by("-paid_at").first()
        reading = checkout_at_payment(last) if last else None
        if reading:
            self.stdout.write(self.style.SUCCESS(f" - [OK] IEO en caja al pagar: {reading.get('ieo')}"))
        else:
            self.stdout.write(self.style.WARNING(" - [REVISAR] no se detectó la lectura en caja del último pago"))

    def _analysis(self, camera):
        return AnalysisSession.objects.create(camera=camera, status=AnalysisSession.Status.COMPLETED,
                                              error_message=TAG, ended_at=timezone.now())

    def _event(self, analysis, table, session, moment, ieo, attention, faces):
        event = DetectionEvent.objects.create(
            session=analysis, faces_count=faces, table=table, service_session=session, occupancy=Decimal(faces),
            valence=Decimal(str(round(_clamp((ieo - 50) / 45, -1, 1), 2))),
            attention_seeking=Decimal(str(round(attention, 2))), experience_index=Decimal(str(round(ieo, 2))),
        )
        self.pending.append((event.pk, moment))