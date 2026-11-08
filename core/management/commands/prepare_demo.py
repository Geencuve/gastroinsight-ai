from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from ai_vision.models import AnalysisSession
from cameras.models import Camera
from operations.models import RestaurantTable
from venues.models import Venue


class Command(BaseCommand):
    help = "Deja la demo lista: ventas y datos visuales recalculados a partir de hoy."

    def handle(self, *args, **options):
        if not Venue.objects.filter(name="Restaurante Demo Santiago").exists():
            self.stdout.write("Creando datos base...")
            call_command("seed_demo_data")

        stale = AnalysisSession.objects.filter(
            status__in=[AnalysisSession.Status.PENDING, AnalysisSession.Status.RUNNING],
        ).update(
            status=AnalysisSession.Status.STOPPED, ended_at=timezone.now(),
            error_message="Detenida al preparar la demo.",
        )
        if stale:
            self.stdout.write(f"Sesiones de análisis pendientes o en curso detenidas: {stale}")

        call_command("seed_demo_sales", reset=True)
        call_command("seed_demo_vision", reset=True)
        call_command("seed_demo_journey", reset=True)
        call_command("generate_dish_images")

        webcam = Camera.objects.filter(name="Webcam de desarrollo").select_related("venue").first()
        if webcam and webcam.table is None:
            webcam.table = RestaurantTable.objects.filter(venue=webcam.venue, code="M01").first()
            webcam.save(update_fields=["table"])

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo lista."))
        self.stdout.write(" - Administrador: admin_demo / AdminDemo123!")
        self.stdout.write(" - Operador:      operador_demo / OperadorDemo123!")
        self.stdout.write(" - Inicia el servidor con: python manage.py runserver")
        self.stdout.write(" - Alerta sostenida en vivo (defensa): python manage.py demo_alerta_sostenida --mesa M04")
