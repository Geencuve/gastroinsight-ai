import csv
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from analytics.views import get_accessible_venues
from authentication.permissions import get_or_create_profile

from .models import AuditLog


def _time_field():
    return next((f.name for f in AuditLog._meta.fields if f.get_internal_type() == "DateTimeField"), "id")


def _date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@login_required
def audit_filtered(request):
    profile = get_or_create_profile(request.user)
    if not (request.user.is_superuser or profile.is_platform_admin):
        raise PermissionDenied("La auditoría es solo para administradores de plataforma.")
    field = _time_field()
    logs = AuditLog.objects.select_related("user", "venue").order_by(f"-{field}")
    params = request.GET
    if params.get("q"):
        logs = logs.filter(Q(description__icontains=params["q"]) | Q(object_type__icontains=params["q"])
                           | Q(user__username__icontains=params["q"]))
    if params.get("usuario"):
        logs = logs.filter(user_id=params["usuario"])
    if params.get("modulo"):
        logs = logs.filter(module=params["modulo"])
    if params.get("accion"):
        logs = logs.filter(action=params["accion"])
    if params.get("local"):
        logs = logs.filter(venue_id=params["local"])
    start, end = _date(params.get("desde")), _date(params.get("hasta"))
    if start and field != "id":
        logs = logs.filter(**{f"{field}__date__gte": start})
    if end and field != "id":
        logs = logs.filter(**{f"{field}__date__lte": end})

    if params.get("formato") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="auditoria_{timezone.localdate():%Y%m%d}.csv"'
        response.write("\ufeff")
        writer = csv.writer(response, delimiter=";")
        writer.writerow(["Fecha", "Usuario", "Acción", "Módulo", "Local", "Objeto", "Descripción", "IP"])
        for log in logs[:20000]:
            moment = getattr(log, field, None)
            writer.writerow([timezone.localtime(moment).strftime("%d-%m-%Y %H:%M:%S") if hasattr(moment, "tzinfo") else "",
                             log.user.username if log.user_id else "sistema", log.get_action_display(), log.module,
                             log.venue.name if log.venue_id else "", f"{log.object_type} {log.object_id}".strip(),
                             log.description, log.ip_address or ""])
        return response

    page = Paginator(logs, 50).get_page(params.get("page"))
    query = params.copy()
    query.pop("page", None)
    return render(request, "monitoring/audit_filtered.html", {
        "page": page, "time_field": field, "querystring": query.urlencode(), "total": logs.count(),
        "users": User.objects.filter(pk__in=AuditLog.objects.values("user_id")).order_by("username"),
        "modules": AuditLog.objects.order_by("module").values_list("module", flat=True).distinct(),
        "actions": AuditLog.Action.choices, "venues": get_accessible_venues(profile), "f": params,
    })
