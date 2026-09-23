from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from ai_vision.models import AnalysisSession, DetectionEvent
from authentication.models import Profile
from cameras.models import Camera
from menus.models import Dish, Menu
from monitoring.models import AuditLog, Incident
from operations.models import (
    RestaurantTable,
    SatisfactionEvaluation,
    ServiceSession,
)
from privacy.models import PrivacyPolicy, ProcessingAuthorization
from venues.models import Venue


class Command(BaseCommand):
    help = (
        "Crea datos de demostración para GastroInsight AI. "
        "No elimina registros existentes."
    )

    def handle(self, *args, **options):
        admin, admin_created = User.objects.get_or_create(
            username="admin_demo",
            defaults={
                "email": "admin_demo@gastroinsight.local",
                "is_staff": True,
                "is_superuser": True,
            },
        )

        if admin_created:
            admin.set_password("AdminDemo123!")
            admin.save()

        profile, _ = Profile.objects.get_or_create(user=admin)
        profile.role = Profile.Role.PLATFORM_ADMIN
        profile.save()

        operator, operator_created = User.objects.get_or_create(
            username="operador_demo",
            defaults={
                "email": "operador@gastroinsight.local",
            },
        )

        if operator_created:
            operator.set_password("OperadorDemo123!")
            operator.save()

        operator_profile, _ = Profile.objects.get_or_create(
            user=operator
        )
        operator_profile.role = Profile.Role.OPERATOR
        operator_profile.save()

        venue, _ = Venue.objects.get_or_create(
            name="Restaurante Demo Santiago",
            defaults={
                "address": "Santiago, Chile",
                "description": (
                    "Local de demostración para GastroInsight AI."
                ),
                "is_active": True,
            },
        )

        operator_profile.venues.add(venue)

        menu, _ = Menu.objects.get_or_create(
            venue=venue,
            name="Carta principal",
            defaults={
                "description": "Menú demostrativo del restaurante.",
                "is_active": True,
            },
        )

        dishes_data = [
            {
                "name": "Salmón a la plancha",
                "category": "Fondo",
                "price": 12990,
            },
            {
                "name": "Risotto de hongos",
                "category": "Fondo",
                "price": 10990,
            },
            {
                "name": "Tiramisú",
                "category": "Postre",
                "price": 5990,
            },
            {
                "name": "Limonada menta-jengibre",
                "category": "Bebida",
                "price": 3990,
            },
        ]

        dishes = {}

        for dish_data in dishes_data:
            dish, _ = Dish.objects.get_or_create(
                menu=menu,
                name=dish_data["name"],
                defaults={
                    "category": dish_data["category"],
                    "price": dish_data["price"],
                    "is_available": True,
                },
            )
            dishes[dish.name] = dish

        tables_data = [
            ("M01", 4, "Salón principal"),
            ("M02", 2, "Salón principal"),
            ("T01", 6, "Terraza"),
        ]

        tables = {}

        for code, capacity, zone_name in tables_data:
            table, _ = RestaurantTable.objects.get_or_create(
                venue=venue,
                code=code,
                defaults={
                    "capacity": capacity,
                    "zone_name": zone_name,
                    "is_active": True,
                },
            )
            tables[code] = table

        camera, _ = Camera.objects.get_or_create(
            venue=venue,
            name="Webcam de desarrollo",
            defaults={
                "source_type": Camera.SourceType.WEBCAM,
                "source": "0",
                "zone_name": "Salón principal",
                "is_active": True,
            },
        )

        policy, _ = PrivacyPolicy.objects.get_or_create(
            venue=venue,
            defaults={
                "version": "1.0",
                "purpose": (
                    "Generar indicadores agregados de ocupación "
                    "y operación sin identificar personas ni "
                    "guardar imágenes originales."
                ),
                "processing_enabled": True,
                "retain_aggregated_events_days": 30,
                "retain_incidents_days": 90,
                "store_original_images": False,
                "updated_by": admin,
            },
        )

        policy.processing_enabled = True
        policy.store_original_images = False
        policy.updated_by = admin
        policy.save()

        ProcessingAuthorization.objects.get_or_create(
            privacy_policy=policy,
            source_description=(
                "Webcam de desarrollo — salón principal"
            ),
            status=ProcessingAuthorization.Status.ACTIVE,
            defaults={
                "authorization_type": (
                    "Autorización interna del establecimiento"
                ),
                "accepted_by": admin,
            },
        )

        today = timezone.localdate()

        sessions_data = [
            (0, "M01", 4, ServiceSession.Status.CLOSED),
            (0, "M02", 2, ServiceSession.Status.CLOSED),
            (-1, "M01", 3, ServiceSession.Status.CLOSED),
            (-2, "T01", 5, ServiceSession.Status.CLOSED),
            (-3, "M02", 2, ServiceSession.Status.CLOSED),
        ]

        service_sessions = []

        for days_offset, table_code, guests_count, status in sessions_data:
            started_at = timezone.now() + timedelta(
                days=days_offset,
                hours=-3,
            )

            service_session, created = ServiceSession.objects.get_or_create(
                table=tables[table_code],
                started_at=started_at,
                defaults={
                    "status": status,
                    "ended_at": started_at + timedelta(hours=1, minutes=20),
                    "guests_count": guests_count,
                    "created_by": operator,
                    "closed_by": operator,
                    "notes": "Sesión generada para demostración.",
                },
            )

            service_sessions.append(service_session)

        evaluation_data = [
            (service_sessions[0], dishes["Salmón a la plancha"], 5),
            (service_sessions[0], dishes["Tiramisú"], 4),
            (service_sessions[1], dishes["Risotto de hongos"], 4),
            (service_sessions[2], dishes["Limonada menta-jengibre"], 3),
            (service_sessions[3], dishes["Salmón a la plancha"], 5),
            (service_sessions[4], dishes["Risotto de hongos"], 2),
        ]

        for service_session, dish, rating in evaluation_data:
            SatisfactionEvaluation.objects.get_or_create(
                service_session=service_session,
                dish=dish,
                rating=rating,
                defaults={
                    "comment": "Evaluación de demostración.",
                    "registered_by": operator,
                },
            )

        for day_offset in range(0, -5, -1):
            created_at = timezone.now() + timedelta(
                days=day_offset,
                hours=-2,
            )

            analysis_session, _ = AnalysisSession.objects.get_or_create(
                camera=camera,
                created_at=created_at,
                defaults={
                    "status": AnalysisSession.Status.COMPLETED,
                    "started_at": created_at,
                    "ended_at": created_at + timedelta(minutes=4),
                    "frames_processed": 180,
                    "total_faces_detected": 265,
                },
            )

            for event_number in range(1, 11):
                event_time = created_at + timedelta(
                    seconds=event_number * 12
                )

                DetectionEvent.objects.get_or_create(
                    session=analysis_session,
                    detected_at=event_time,
                    defaults={
                        "faces_count": (event_number % 4) + 1,
                        "processing_time_ms": 24 + event_number,
                    },
                )

        Incident.objects.get_or_create(
            venue=venue,
            module="ai_vision",
            title="Fuente visual no disponible",
            defaults={
                "description": (
                    "Incidencia de prueba para verificar el "
                    "módulo de monitoreo."
                ),
                "severity": Incident.Severity.WARNING,
                "status": Incident.Status.OPEN,
                "technical_details": {
                    "source": "webcam",
                    "test_data": True,
                },
            },
        )

        AuditLog.objects.get_or_create(
            user=admin,
            venue=venue,
            action=AuditLog.Action.CREATE,
            module="core",
            object_type="DemoData",
            object_id="seed_demo_data",
            defaults={
                "description": (
                    "Se generaron datos de demostración del prototipo."
                ),
                "ip_address": "127.0.0.1",
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Datos de demostración creados correctamente."
            )
        )

        self.stdout.write(
            "Usuarios de prueba:"
        )

        self.stdout.write(
            " - admin_demo / AdminDemo123!"
        )

        self.stdout.write(
            " - operador_demo / OperadorDemo123!"
        )