from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls", namespace="core")),
    path("auth/",include("authentication.urls", namespace="authentication")),
    path("venues/", include("venues.urls", namespace="venues")),
    path("menus/", include("menus.urls", namespace="menus")),
    path("cameras/", include("cameras.urls", namespace="cameras")),
    path("ai/", include("ai_vision.urls", namespace="ai_vision")),
    path("analytics/", include("analytics.urls", namespace="analytics")),
    path("reports/", include("reports.urls", namespace="reports")),
    path("operations/", include("operations.urls", namespace="operations")),
    path("monitoring/", include("monitoring.urls", namespace="monitoring")),
    path("privacy/", include("privacy.urls", namespace="privacy")),
    path("api/", include("api.urls", namespace="api")),
    path("assistant/", include("assistant_chat.urls", namespace="assistant_chat")),
    path("sales/", include("sales.urls", namespace="sales")),
    path("opinion/", include("operations.feedback_urls", namespace="feedback")),
    path("sala/", include("operations.floor_urls")),
    path("caja/", include("operations.cashier_urls")),
    path("cocina/", include(("sales.kds_urls", "kds"), namespace="kitchen")),
    path("barra/", include(("sales.kds_urls", "kds"), namespace="bar")),
]
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
elif settings.SERVE_MEDIA:
    # Publicación temporal (túnel): sirve las fotos de los platos sin modo DEBUG.
    from django.urls import re_path
    from django.views.static import serve

    urlpatterns += [re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})]

if not settings.DEBUG and getattr(settings, "SERVE_STATIC", False):
    # Versión de escritorio: sirve los archivos estáticos recopilados.
    from django.urls import re_path
    from django.views.static import serve as static_serve

    urlpatterns += [re_path(r"^static/(?P<path>.*)$", static_serve, {"document_root": settings.STATIC_ROOT})]
