import random
import time
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from ai_vision.services.association import find_service_session
from ai_vision.services.experience import experience_index, wait_minutes
from cameras.models import Camera


def clamp(value, low, high):
    return max(low, min(high, value))


def dec(value, places=4):
    return Decimal(str(round(value, places)))


class Command(BaseCommand):
    help = "Simula lecturas en vivo (datos SINTÉTICOS) de las cámaras demo para el Monitor en vivo."

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=float, default=10, help="Duración de la simulación (por defecto 10).")
        parser.add_argument("--interval", type=float, default=3.0, help="Segundos entre lecturas (por defecto 3).")
        parser.add_argument("--ticks", type=int, default=0, help="Detener tras N lecturas; 0 = según --minutes.")
        parser.add_argument("--seed", type=int, default=7)

    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        cameras = list(Camera.objects.filter(
            source_type=Camera.SourceType.DEMO, is_active=True, table__isnull=False,
        ).select_related("table"))
        if not cameras:
            raise CommandError("No hay cámaras demo con mesa. Ejecuta: python manage.py seed_demo_vision")

        now = timezone.now()
        sessions = {}
        for camera in cameras:
            AnalysisSession.objects.filter(camera=camera, status=AnalysisSession.Status.RUNNING).update(
                status=AnalysisSession.Status.STOPPED, ended_at=now,
            )
            sessions[camera.id] = AnalysisSession.objects.create(
                camera=camera, status=AnalysisSession.Status.RUNNING, started_at=now,
                error_message="Simulación en vivo con datos sintéticos.",
            )

        # La mesa con atención abierta (si existe) empeora durante la simulación, para mostrar las alertas.
        troubled = next((c.id for c in cameras if find_service_session(c.table, now)), cameras[0].id)
        state = {
            c.id: {"valence": rng.uniform(0.10, 0.35), "attention": rng.uniform(0.03, 0.10),
                   "occupancy": rng.choice([2, 2, 3, 4])}
            for c in cameras
        }
        deadline = time.monotonic() + options["minutes"] * 60
        counts = {c.id: 0 for c in cameras}
        tick = 0
        self.stdout.write(self.style.SUCCESS(f"Simulando {len(cameras)} mesas demo (datos sintéticos). Ctrl+C para detener."))
        try:
            while time.monotonic() < deadline and (not options["ticks"] or tick < options["ticks"]):
                tick += 1
                for camera in cameras:
                    s = state[camera.id]
                    worsening = camera.id == troubled and tick > 8
                    s["valence"] = clamp(s["valence"] + rng.gauss(-0.03 if worsening else 0.0, 0.04), -0.6, 0.8)
                    s["attention"] = clamp(s["attention"] + rng.gauss(0.03 if worsening else -0.004, 0.025), 0.0, 0.8)
                    if rng.random() < 0.08:
                        s["occupancy"] = clamp(s["occupancy"] + rng.choice([-1, 1]), 1, 6)
                    moment = timezone.now()
                    service = find_service_session(camera.table, moment)
                    total = s["occupancy"] * 12
                    happy = round(total * clamp(0.15 + s["valence"] * 0.5, 0.02, 0.9))
                    negative = round(total * clamp(0.08 - s["valence"] * 0.2, 0.0, 0.6))
                    distribution = {"happy": happy, "sad": negative // 2, "angry": negative - negative // 2,
                                    "neutral": max(0, total - happy - negative)}
                    distribution = {k: v for k, v in distribution.items() if v}
                    index = experience_index(s["valence"], s["attention"], wait_minutes(service, moment))
                    DetectionEvent.objects.create(
                        session=sessions[camera.id], detected_at=moment, faces_count=s["occupancy"],
                        estimated_emotion=max(distribution, key=distribution.get) if distribution else "unknown",
                        confidence=dec(rng.uniform(0.72, 0.9)), detector_confidence=dec(rng.uniform(0.8, 0.95)),
                        emotion_distribution=distribution, processing_time_ms=rng.randint(30, 60),
                        table=camera.table, service_session=service,
                        occupancy=dec(s["occupancy"], 2), presence_ratio=dec(rng.uniform(0.85, 1.0)),
                        activity_level=dec(clamp(rng.gauss(22, 7), 3, 100), 2),
                        valence=dec(s["valence"]), attention_seeking=dec(s["attention"]),
                        experience_index=Decimal(str(index)) if index is not None else None,
                    )
                    counts[camera.id] += 1
                self.stdout.write(f"[{timezone.localtime().strftime('%H:%M:%S')}] lectura {tick}: {len(cameras)} mesas")
                if options["interval"]:
                    time.sleep(options["interval"])
        except KeyboardInterrupt:
            self.stdout.write("Simulación detenida.")
        finally:
            end = timezone.now()
            for camera in cameras:
                AnalysisSession.objects.filter(pk=sessions[camera.id].pk).update(
                    status=AnalysisSession.Status.COMPLETED, ended_at=end,
                    frames_processed=counts[camera.id] * 15,
                    total_faces_detected=counts[camera.id] * state[camera.id]["occupancy"] * 15,
                )
        self.stdout.write(self.style.SUCCESS("Simulación finalizada."))
