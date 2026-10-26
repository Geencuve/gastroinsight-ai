import random
from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ai_vision.models import AnalysisSession, DetectionEvent
from cameras.models import Camera
from operations.models import RestaurantTable, ServiceSession
from venues.models import Venue

SALES_TAG = "Generado automáticamente para demo."
CAMERA_NOTE = "Cámara de demostración: genera datos SINTÉTICOS, no procesa video real."
DEMO_TABLES = ("M02", "M03", "M04", "T01")
NEGATIVE = ("sad", "angry", "disgust", "fear", "contempt")
NEGATIVE_WEIGHTS = (5, 3, 1, 1, 1)


class Command(BaseCommand):
    help = (
        "Genera sesiones de análisis y eventos visuales SINTÉTICOS asociados a las "
        "sesiones de atención demo. Solo para demostrar el panel de correlación."
    )

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Borra y regenera los datos visuales demo.")
        parser.add_argument("--effect", type=float, default=1.0,
                            help="Intensidad de la relación sintética Ts-expresiones (0 = sin relación).")

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(2026)
        effect = options["effect"]
        venue = Venue.objects.filter(name="Restaurante Demo Santiago").first()
        if venue is None:
            raise CommandError("Primero ejecuta: python manage.py seed_demo_data y seed_demo_sales")

        cameras = []
        for code in DEMO_TABLES:
            table = RestaurantTable.objects.filter(venue=venue, code=code).first()
            if table is None:
                continue
            camera, _ = Camera.objects.get_or_create(
                venue=venue, name=f"Cámara demo {code}",
                defaults={
                    "source_type": Camera.SourceType.DEMO, "source": "demo",
                    "zone_name": table.zone_name, "table": table,
                    "notes": CAMERA_NOTE, "is_active": True,
                },
            )
            cameras.append(camera)

        existing = AnalysisSession.objects.filter(camera__in=cameras)
        if options["reset"]:
            count = existing.count()
            existing.delete()
            self.stdout.write(f"Reset: {count} sesiones de análisis demo eliminadas.")
        elif existing.exists():
            self.stdout.write(self.style.WARNING("Ya existen datos visuales demo. Usa --reset para regenerarlos."))
            return

        total_sessions = total_events = 0
        for camera in cameras:
            services = ServiceSession.objects.filter(
                table=camera.table, notes=SALES_TAG,
                status=ServiceSession.Status.CLOSED, ended_at__isnull=False,
            )
            for service in services:
                start, end = service.started_at, service.ended_at
                ts_minutes = (end - start).total_seconds() / 60
                excess = (ts_minutes - 75) / 35  # aprox. -0,9 a +1,0 según Ts

                p_neg = min(0.45, max(0.02, 0.10 + 0.08 * effect * excess + rng.gauss(0, 0.03)))
                p_pos = min(0.50, max(0.03, 0.22 - 0.08 * effect * excess + rng.gauss(0, 0.04)))
                p_sur = 0.03

                analysis = AnalysisSession.objects.create(
                    camera=camera, status=AnalysisSession.Status.COMPLETED,
                    started_at=start, ended_at=end,
                    error_message="Datos sintéticos de demostración.",
                )

                events, frames, faces_total = [], 0, 0
                moment = start + timedelta(seconds=rng.randint(30, 90))
                while moment < end:
                    faces = max(0, min(service.guests_count,
                                       int(round(rng.gauss(service.guests_count * 0.8, 0.7)))))
                    distribution = Counter()
                    for _ in range(faces * rng.randint(10, 15)):
                        r = rng.random()
                        if r < p_pos:
                            distribution["happy"] += 1
                        elif r < p_pos + p_neg:
                            distribution[rng.choices(NEGATIVE, weights=NEGATIVE_WEIGHTS)[0]] += 1
                        elif r < p_pos + p_neg + p_sur:
                            distribution["surprised"] += 1
                        else:
                            distribution["neutral"] += 1
                    has_faces = bool(distribution)
                    events.append(DetectionEvent(
                        session=analysis, detected_at=moment, faces_count=faces,
                        estimated_emotion=distribution.most_common(1)[0][0] if has_faces else "unknown",
                        confidence=Decimal(str(round(rng.uniform(0.70, 0.92), 4))) if has_faces else None,
                        detector_confidence=Decimal(str(round(rng.uniform(0.78, 0.95), 4))) if has_faces else None,
                        emotion_distribution=dict(distribution),
                        processing_time_ms=rng.randint(32, 70),
                        table=camera.table, service_session=service,
                    ))
                    frames += 15
                    faces_total += sum(distribution.values())
                    moment += timedelta(seconds=rng.randint(60, 120))

                DetectionEvent.objects.bulk_create(events)
                AnalysisSession.objects.filter(pk=analysis.pk).update(
                    created_at=start, frames_processed=frames, total_faces_detected=faces_total,
                )
                total_sessions += 1
                total_events += len(events)

        self.stdout.write(self.style.SUCCESS("Datos visuales SINTÉTICOS de demostración creados."))
        self.stdout.write(f" - Cámaras demo: {', '.join(c.name for c in cameras)}")
        self.stdout.write(f" - Sesiones de análisis: {total_sessions}")
        self.stdout.write(f" - Eventos visuales: {total_events}")
        self.stdout.write(f" - Intensidad de relación sintética (--effect): {effect}")
