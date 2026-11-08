"""Reproduce en vivo la alerta por umbral sostenido (ejemplo de la docente: 80 % durante 12 minutos).

    python manage.py demo_alerta_sostenida --mesa M04 --minutos 13   -> SÍ alerta
    python manage.py demo_alerta_sostenida --mesa M04 --minutos 10   -> NO alerta
    python manage.py demo_alerta_sostenida --limpiar                 -> borra las lecturas
"""
import time
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from cameras.models import Camera
from operations.models import AlertSettings, RestaurantTable
from operations.services.sustained import impatience, sustained_impatience

TAG = "Datos sintéticos de demostración (alerta sostenida)."
CAMERA_NOTE = "Cámara de demostración: genera datos SINTÉTICOS, no procesa video real."
ATTENTION, IEO = 0.9, 15


class Command(BaseCommand):
    help = "Carga lecturas SINTÉTICAS de impaciencia en una mesa para mostrar la alerta sostenida en vivo."

    def add_arguments(self, parser):
        parser.add_argument("--mesa", default="M04")
        parser.add_argument("--local", default="", help="Parte del nombre del local, si hay varios.")
        parser.add_argument("--umbral", type=int, default=80, help="Umbral de impaciencia (%%).")
        parser.add_argument("--sostenido", type=int, default=12, help="Minutos que debe sostenerse.")
        parser.add_argument("--minutos", type=int, default=13, help="Minutos de lecturas a cargar hacia atrás.")
        parser.add_argument("--sin-seguir", action="store_true", dest="sin_seguir",
                            help="No seguir enviando lecturas cada 15 s.")
        parser.add_argument("--limpiar", action="store_true", help="Borra las lecturas de esta demostración.")

    def handle(self, *args, mesa="M04", local="", umbral=80, sostenido=12, minutos=13, sin_seguir=False,
               limpiar=False, **options):
        previous = AnalysisSession.objects.filter(error_message=TAG)
        if limpiar:
            count = DetectionEvent.objects.filter(session__in=previous).count()
            DetectionEvent.objects.filter(session__in=previous).delete()
            previous.delete()
            self.stdout.write(self.style.SUCCESS(f"[OK] {count} lecturas de la demostración eliminadas."))
            return
        if not (1 <= minutos <= 60 and 1 <= sostenido <= 60 and 1 <= umbral <= 100):
            raise CommandError("Usa minutos y sostenido entre 1 y 60, y umbral entre 1 y 100.")
        tables = RestaurantTable.objects.filter(code__iexact=mesa).select_related("venue")
        if local:
            tables = tables.filter(venue__name__icontains=local)
        table = tables.first()
        if table is None:
            raise CommandError(f"No existe la mesa «{mesa}».")

        cfg, _ = AlertSettings.objects.get_or_create(venue=table.venue)
        before = (cfg.impatience_pct, cfg.impatience_minutes)
        cfg.impatience_pct, cfg.impatience_minutes = umbral, sostenido
        cfg.save()

        camera = Camera.objects.filter(venue=table.venue, table=table).first() or Camera.objects.create(
            venue=table.venue, name=f"Cámara demo {table.code}", source_type=Camera.SourceType.DEMO,
            source=f"demo-{table.code.lower()}", table=table, notes=CAMERA_NOTE)
        DetectionEvent.objects.filter(session__in=previous).delete()
        previous.delete()
        analysis = AnalysisSession.objects.create(camera=camera, status=AnalysisSession.Status.RUNNING, error_message=TAG)

        now = timezone.now()
        steps = minutos * 2
        for i in range(steps + 1):
            self._event(analysis, table, now - timedelta(seconds=30 * (steps - i)))

        self.stdout.write(f"Mesa {table.code} ({table.venue.name}) · umbral {umbral} % durante {sostenido} min "
                          f"(antes: {before[0]} % durante {before[1]} min)")
        self.stdout.write(f"Lecturas cargadas: {minutos} min, una cada 30 s · índice de impaciencia = {impatience(ATTENTION, IEO)}")
        result = sustained_impatience(table, cfg)
        if result:
            self.stdout.write(self.style.SUCCESS(f"[SÍ ALERTA] impaciencia {result[0]} % durante {result[1]} min: "
                                                 f"supera {umbral} % por más de {sostenido} min."))
        else:
            self.stdout.write(self.style.WARNING(f"[NO ALERTA] {minutos} min no alcanzan los {sostenido} min sostenidos "
                                                 "(es lo esperado si minutos < sostenido)."))
        self.stdout.write("Para volver a los valores recomendados: Centro de gestión → 🔔 Alertas → ↺ Valores recomendados.")

        if sin_seguir:
            AnalysisSession.objects.filter(pk=analysis.pk).update(status=AnalysisSession.Status.STOPPED, ended_at=timezone.now())
            return
        self.stdout.write("Enviando una lectura cada 15 s para mantener la mesa en vivo. Mira la campana o «Mis alertas». "
                          "Ctrl + C para terminar.")
        try:
            while True:
                time.sleep(15)
                self._event(analysis, table, timezone.now())
        except KeyboardInterrupt:
            self.stdout.write("Demostración detenida. Borra las lecturas con: python manage.py demo_alerta_sostenida --limpiar")
        finally:
            AnalysisSession.objects.filter(pk=analysis.pk).update(status=AnalysisSession.Status.STOPPED, ended_at=timezone.now())

    def _event(self, analysis, table, moment):
        event = DetectionEvent.objects.create(
            session=analysis, faces_count=2, table=table, occupancy=Decimal(2), valence=Decimal("-0.6"),
            attention_seeking=Decimal(str(ATTENTION)), experience_index=Decimal(IEO))
        DetectionEvent.objects.filter(pk=event.pk).update(detected_at=moment)