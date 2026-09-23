from rest_framework import permissions, viewsets

from ai_vision.models import AnalysisSession, DetectionEvent
from cameras.models import Camera
from menus.models import Dish, Menu
from operations.models import (
    RestaurantTable,
    SatisfactionEvaluation,
    ServiceSession,
)
from venues.models import Venue

from .permissions import get_accessible_venues
from .serializers import (
    AnalysisSessionSerializer,
    CameraSerializer,
    DetectionEventSerializer,
    DishSerializer,
    MenuSerializer,
    RestaurantTableSerializer,
    SatisfactionEvaluationSerializer,
    ServiceSessionSerializer,
    VenueSerializer,
)


class BaseScopedViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_accessible_venues(self):
        return get_accessible_venues(self.request.user)


class VenueViewSet(BaseScopedViewSet):
    serializer_class = VenueSerializer

    def get_queryset(self):
        return self.get_accessible_venues().order_by("name")


class MenuViewSet(BaseScopedViewSet):
    serializer_class = MenuSerializer

    def get_queryset(self):
        return (
            Menu.objects.filter(
                venue__in=self.get_accessible_venues(),
                is_active=True,
            )
            .select_related("venue")
            .order_by("venue__name", "name")
        )


class DishViewSet(BaseScopedViewSet):
    serializer_class = DishSerializer

    def get_queryset(self):
        return (
            Dish.objects.filter(
                menu__venue__in=self.get_accessible_venues(),
                menu__is_active=True,
                is_available=True,
            )
            .select_related("menu", "menu__venue")
            .order_by(
                "menu__venue__name",
                "menu__name",
                "name",
            )
        )


class CameraViewSet(BaseScopedViewSet):
    serializer_class = CameraSerializer

    def get_queryset(self):
        return (
            Camera.objects.filter(
                venue__in=self.get_accessible_venues(),
                is_active=True,
            )
            .select_related("venue")
            .order_by("venue__name", "name")
        )


class RestaurantTableViewSet(BaseScopedViewSet):
    serializer_class = RestaurantTableSerializer

    def get_queryset(self):
        return (
            RestaurantTable.objects.filter(
                venue__in=self.get_accessible_venues(),
            )
            .select_related("venue")
            .order_by("venue__name", "code")
        )


class ServiceSessionViewSet(BaseScopedViewSet):
    serializer_class = ServiceSessionSerializer

    def get_queryset(self):
        return (
            ServiceSession.objects.filter(
                table__venue__in=self.get_accessible_venues(),
            )
            .select_related(
                "table",
                "table__venue",
                "created_by",
                "closed_by",
            )
            .order_by("-started_at")
        )


class SatisfactionEvaluationViewSet(BaseScopedViewSet):
    serializer_class = SatisfactionEvaluationSerializer

    def get_queryset(self):
        return (
            SatisfactionEvaluation.objects.filter(
                service_session__table__venue__in=(
                    self.get_accessible_venues()
                ),
            )
            .select_related(
                "service_session",
                "service_session__table",
                "service_session__table__venue",
                "dish",
                "dish__menu",
                "registered_by",
            )
            .order_by("-created_at")
        )


class AnalysisSessionViewSet(BaseScopedViewSet):
    serializer_class = AnalysisSessionSerializer

    def get_queryset(self):
        return (
            AnalysisSession.objects.filter(
                camera__venue__in=self.get_accessible_venues(),
            )
            .select_related(
                "camera",
                "camera__venue",
            )
            .order_by("-created_at")
        )


class DetectionEventViewSet(BaseScopedViewSet):
    serializer_class = DetectionEventSerializer

    def get_queryset(self):
        return (
            DetectionEvent.objects.filter(
                session__camera__venue__in=(
                    self.get_accessible_venues()
                ),
            )
            .select_related(
                "session",
                "session__camera",
                "session__camera__venue",
            )
            .order_by("-detected_at")
        )