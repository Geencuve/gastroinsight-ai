"""Asociación espacio-temporal entre eventos visuales y sesiones de atención."""
from django.db.models import Q

from operations.models import ServiceSession


def find_service_session(table, moment):
    """Retorna la sesión de atención activa en la mesa en ese instante, o None."""
    if table is None:
        return None
    return (
        ServiceSession.objects.filter(table=table, started_at__lte=moment)
        .filter(Q(ended_at__isnull=True) | Q(ended_at__gte=moment))
        .exclude(status=ServiceSession.Status.CANCELLED)
        .order_by("-started_at")
        .first()
    )
