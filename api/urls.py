from rest_framework.routers import DefaultRouter

from .views import (
    AnalysisSessionViewSet,
    CameraViewSet,
    DetectionEventViewSet,
    DishViewSet,
    MenuViewSet,
    RestaurantTableViewSet,
    SatisfactionEvaluationViewSet,
    ServiceSessionViewSet,
    VenueViewSet,
)

app_name = "api"

router = DefaultRouter()

router.register("venues", VenueViewSet, basename="venue")
router.register("menus", MenuViewSet, basename="menu")
router.register("dishes", DishViewSet, basename="dish")
router.register("cameras", CameraViewSet, basename="camera")
router.register("tables", RestaurantTableViewSet, basename="table")
router.register(
    "service-sessions",
    ServiceSessionViewSet,
    basename="service-session",
)
router.register(
    "evaluations",
    SatisfactionEvaluationViewSet,
    basename="evaluation",
)
router.register(
    "analysis-sessions",
    AnalysisSessionViewSet,
    basename="analysis-session",
)
router.register(
    "detection-events",
    DetectionEventViewSet,
    basename="detection-event",
)

urlpatterns = router.urls