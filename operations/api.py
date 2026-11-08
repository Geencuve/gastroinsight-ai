"""
API de integración v1 de GastroInsight AI.
- GET  /api/v1/estado/      verifica la clave.
- POST /api/v1/telemetria/  métricas agregadas de un nodo de cámara (nunca imágenes).
- POST /api/v1/ventas/      ventas pagadas desde el sistema de caja del local.
Autenticación: cabecera «Authorization: Bearer gi_…». Cada clave solo accede a su local.
"""
import hashlib
import json
import secrets
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

MAX_BODY = 256 * 1024
RATE_LIMIT = 120


def hash_key(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_key():
    raw = "gi_" + secrets.token_urlsafe(32)
    return raw, raw[:10], hash_key(raw)


class ApiError(Exception):
    def __init__(self, status, message, details=None):
        super().__init__(message)
        self.status, self.message, self.details = status, message, details


def _authenticate(request):
    from .models import ApiKey

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise ApiError(401, "Falta la clave: usa la cabecera «Authorization: Bearer gi_…».")
    key = ApiKey.objects.select_related("venue").filter(key_hash=hash_key(header[7:].strip()), is_active=True).first()
    if key is None:
        raise ApiError(401, "Clave inválida o revocada.")
    bucket = f"gi-api-{key.pk}-{timezone.now():%Y%m%d%H%M}"
    if not cache.add(bucket, 1, 70):
        try:
            if cache.incr(bucket) > RATE_LIMIT:
                raise ApiError(429, f"Límite de {RATE_LIMIT} solicitudes por minuto superado.")
        except ValueError:
            cache.set(bucket, 1, 70)
    type(key).objects.filter(pk=key.pk).update(last_used_at=timezone.now())
    return key


def _payload(request):
    if len(request.body) > MAX_BODY:
        raise ApiError(413, "El cuerpo supera los 256 KB.")
    if not request.content_type.startswith("application/json"):
        raise ApiError(415, "Envía JSON con «Content-Type: application/json». La API no acepta imágenes.")
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        raise ApiError(400, "JSON inválido.")
    if not isinstance(data, dict):
        raise ApiError(400, "Se esperaba un objeto JSON.")
    return data


def _number(data, field, low, high, required=False, integer=False):
    value = data.get(field)
    if value is None:
        if required:
            raise ApiError(400, f"Falta el campo «{field}».")
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ApiError(400, f"«{field}» debe ser numérico.")
    if not (Decimal(str(low)) <= number <= Decimal(str(high))):
        raise ApiError(400, f"«{field}» debe estar entre {low} y {high}.")
    return int(number) if integer else number


def _moment(data, field):
    if not data.get(field):
        return timezone.now()
    moment = parse_datetime(str(data[field]))
    if moment is None:
        raise ApiError(400, f"«{field}» debe ser una fecha ISO 8601 (ej. 2026-11-07T20:15:00-03:00).")
    return moment if timezone.is_aware(moment) else timezone.make_aware(moment)


def _endpoint(handler):
    @csrf_exempt
    def view(request, *args, **kwargs):
        try:
            key = _authenticate(request)
            return handler(request, key, *args, **kwargs)
        except ApiError as error:
            body = {"ok": False, "error": error.message}
            if error.details:
                body["detalles"] = error.details
            return JsonResponse(body, status=error.status)
    view.__name__ = handler.__name__
    return view


@require_http_methods(["GET"])
@_endpoint
def status(request, key):
    return JsonResponse({"ok": True, "local": key.venue.name, "clave": key.name, "version": "v1"})


@require_http_methods(["POST"])
@_endpoint
def telemetry(request, key):
    from ai_vision.models import AnalysisSession, DetectionEvent
    from cameras.models import Camera

    from .models import RestaurantTable, ServiceSession

    data = _payload(request)
    camera_id = _number(data, "camara", 1, 10**9, required=True, integer=True)
    camera = Camera.objects.filter(pk=camera_id, venue=key.venue).select_related("table").first()
    if camera is None:
        raise ApiError(404, "La cámara no existe en el local de esta clave.")
    table = camera.table
    if data.get("mesa"):
        table = RestaurantTable.objects.filter(venue=key.venue, code=str(data["mesa"])[:20]).first()
        if table is None:
            raise ApiError(404, "La mesa no existe en el local de esta clave.")
    faces = _number(data, "rostros", 0, 100, integer=True) or 0
    valence = _number(data, "ibe", -1, 1)
    attention = _number(data, "atencion", 0, 1)
    ieo = _number(data, "ieo", 0, 100)
    if ieo is None and (valence is not None or attention is not None):
        from ai_vision.services.experience import experience_index

        computed = experience_index(float(valence) if valence is not None else None,
                                    float(attention) if attention is not None else None)
        ieo = Decimal(str(round(computed, 2))) if computed is not None else None
    analysis = (AnalysisSession.objects.filter(camera=camera, status="running").order_by("-id").first()
                or AnalysisSession.objects.create(camera=camera, status="running"))
    session = (ServiceSession.objects.filter(table=table, status=ServiceSession.Status.OPEN).first() if table else None)
    event = DetectionEvent.objects.create(
        session=analysis, faces_count=faces, table=table, service_session=session,
        occupancy=_number(data, "personas", 0, 100) or Decimal(faces), valence=valence, attention_seeking=attention,
        experience_index=ieo, persons_detected=_number(data, "personas_yolo", 0, 200),
    )
    moment = _moment(data, "momento")
    DetectionEvent.objects.filter(pk=event.pk).update(detected_at=moment)
    return JsonResponse({"ok": True, "evento": event.pk, "ieo": float(ieo) if ieo is not None else None}, status=201)


@require_http_methods(["POST"])
@_endpoint
def sales(request, key):
    from menus.models import Dish
    from sales.models import Order, OrderItem

    from .models import ExternalSale, RestaurantTable, ServiceSession

    data = _payload(request)
    external_id = str(data.get("pedido_externo") or "").strip()[:100]
    if not external_id:
        raise ApiError(400, "Falta «pedido_externo» (identificador del pedido en tu sistema de caja).")
    existing = ExternalSale.objects.filter(venue=key.venue, external_id=external_id).first()
    if existing:
        return JsonResponse({"ok": True, "duplicado": True, "pedido": existing.order_id})
    table = RestaurantTable.objects.filter(venue=key.venue, code=str(data.get("mesa") or "")[:20]).first()
    if table is None:
        raise ApiError(404, "La mesa no existe en el local de esta clave.")
    items = data.get("items")
    if not isinstance(items, list) or not items or len(items) > 100:
        raise ApiError(400, "«items» debe ser una lista de 1 a 100 platos.")
    quantities, unknown = {}, []
    for item in items:
        name = str((item or {}).get("plato") or "").strip()
        dish = Dish.objects.filter(menu__venue=key.venue, name__iexact=name).first()
        if dish is None:
            unknown.append(name or "(sin nombre)")
            continue
        quantities[dish] = quantities.get(dish, 0) + _number(item, "cantidad", 1, 999, required=True, integer=True)
    if unknown:
        raise ApiError(400, "Hay platos que no existen en la carta del local.", {"desconocidos": unknown})
    paid_at = _moment(data, "fecha_pago")
    guests = _number(data, "comensales", 1, 50, integer=True) or 1
    creator = key.created_by or type(key)._meta.get_field("created_by").related_model.objects.filter(is_superuser=True).first()
    if creator is None:
        raise ApiError(409, "La clave no tiene un responsable: créala de nuevo desde el Centro de gestión.")

    payment = ""
    choices = Order._meta.get_field("payment_method").choices or []
    wanted = str(data.get("medio_pago") or "").strip().lower()
    for value, label in choices:
        if value and wanted and (wanted == str(value).lower() or wanted in str(label).lower()):
            payment = value
            break

    with transaction.atomic():
        session = ServiceSession.objects.create(table=table, guests_count=guests)
        session_fields = {f.name for f in ServiceSession._meta.fields}
        updates = {"status": ServiceSession.Status.CLOSED, "started_at": paid_at - timedelta(minutes=45)}
        for name in ("ended_at", "closed_at"):
            if name in session_fields:
                updates[name] = paid_at
        ServiceSession.objects.filter(pk=session.pk).update(**updates)
        order = Order.objects.create(service_session=session, created_by=creator)
        subtotal = Decimal("0")
        for dish, quantity in quantities.items():
            line = OrderItem.objects.create(order=order, dish=dish, quantity=quantity)
            line.refresh_from_db()
            total = line.line_total or (dish.price * quantity)
            OrderItem.objects.filter(pk=line.pk).update(line_total=total, prep_status="delivered", delivered_at=paid_at)
            subtotal += Decimal(total)
        Order.objects.filter(pk=order.pk).update(status=Order.Status.PAID, subtotal=subtotal, total=subtotal,
                                                 confirmed_at=paid_at - timedelta(minutes=40), paid_at=paid_at,
                                                 payment_method=payment)
        ExternalSale.objects.create(venue=key.venue, external_id=external_id, order=order)
    return JsonResponse({"ok": True, "pedido": order.pk, "total": int(subtotal)}, status=201)
