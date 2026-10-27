from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from authentication.permissions import (
    get_or_create_profile,
    user_can_access_venue,
)
from monitoring.models import AuditLog
from monitoring.services.audit import log_action
from menus.services import build_dish_cards
from operations.models import ServiceSession

from .forms import (
    OrderCreateForm,
    OrderDiscountForm,
    OrderItemForm,
    PaymentForm,
)
from .models import Order, OrderItem


def user_can_operate_sales(user):
    profile = get_or_create_profile(user)

    return (
        profile.is_platform_admin
        or profile.is_venue_admin
        or profile.role == profile.Role.OPERATOR
    )


def get_order_for_user_or_404(user, order_id):
    order = get_object_or_404(
        Order.objects.select_related(
            "service_session",
            "service_session__table",
            "service_session__table__venue",
            "created_by",
        ).prefetch_related(
            "items",
            "items__dish",
        ),
        id=order_id,
    )

    venue = order.service_session.table.venue

    if not user_can_access_venue(user, venue):
        raise PermissionDenied(
            "No tienes acceso al local asociado a este pedido."
        )

    return order


@login_required
def order_list(request):
    profile = get_or_create_profile(request.user)

    queryset = (
        Order.objects.select_related(
            "service_session",
            "service_session__table",
            "service_session__table__venue",
            "created_by",
        )
        .order_by("-opened_at")
    )

    if not profile.is_platform_admin:
        queryset = queryset.filter(
            service_session__table__venue__in=profile.venues.all()
        )

    venue_id = request.GET.get("venue")
    status_value = request.GET.get("status")

    if venue_id:
        queryset = queryset.filter(
            service_session__table__venue_id=venue_id
        )

    if status_value in Order.Status.values:
        queryset = queryset.filter(status=status_value)

    return render(
        request,
        "sales/order_list.html",
        {
            "orders": queryset[:100],
            "status_choices": Order.Status.choices,
            "selected_venue": venue_id or "",
            "selected_status": status_value or "",
        },
    )


@login_required
def order_create(request):
    if not user_can_operate_sales(request.user):
        raise PermissionDenied(
            "Tu rol no permite crear pedidos."
        )

    form = OrderCreateForm(
        request.POST or None,
        user=request.user,
    )

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            order = form.save(commit=False)
            order.created_by = request.user
            order.full_clean()
            order.save()

            log_action(
                request,
                action=AuditLog.Action.CREATE,
                module="sales",
                venue=order.service_session.table.venue,
                object_type="Order",
                object_id=order.id,
                description=(
                    f"Creó el pedido #{order.id} para la mesa "
                    f"{order.service_session.table.code}."
                ),
            )

        messages.success(
            request,
            f"Pedido #{order.id} creado. Agrega sus productos.",
        )

        return redirect(
            "sales:order_detail",
            order_id=order.id,
        )

    return render(
        request,
        "sales/order_form.html",
        {
            "form": form,
            "title": "Crear pedido",
        },
    )


@login_required
def order_detail(request, order_id):
    order = get_order_for_user_or_404(
        request.user,
        order_id,
    )

    can_operate = user_can_operate_sales(request.user)

    item_form = OrderItemForm(order=order)
    discount_form = OrderDiscountForm(instance=order)
    payment_form = PaymentForm()

    return render(
        request,
        "sales/order_detail.html",
        {
            "order": order,
            "can_operate": can_operate,
            "item_form": item_form,
            "discount_form": discount_form,
            "payment_form": payment_form,
            "dish_cards": (
                build_dish_cards(list(item_form.fields["dish"].queryset))
                if order.can_be_edited else []
            ),
        },
    )


@login_required
@require_POST
def order_item_add(request, order_id):
    if not user_can_operate_sales(request.user):
        raise PermissionDenied(
            "Tu rol no permite modificar pedidos."
        )

    order = get_order_for_user_or_404(
        request.user,
        order_id,
    )

    form = OrderItemForm(
        request.POST,
        order=order,
    )

    if form.is_valid():
        try:
            with transaction.atomic():
                item = form.save(commit=False)
                item.order = order
                item.full_clean()
                item.save()

                order.refresh_from_db()

                log_action(
                    request,
                    action=AuditLog.Action.CREATE,
                    module="sales",
                    venue=order.service_session.table.venue,
                    object_type="OrderItem",
                    object_id=item.id,
                    description=(
                        f"Agregó {item.quantity} × "
                        f"{item.dish_name} al pedido #{order.id}."
                    ),
                )

            messages.success(
                request,
                f"Se agregó {item.quantity} × {item.dish_name}.",
            )

        except ValidationError as error:
            messages.error(request, error.messages[0])

    else:
        messages.error(
            request,
            "No se pudo agregar el ítem. "
            + " ".join(e for errs in form.errors.values() for e in errs),
        )

    return redirect(
        "sales:order_detail",
        order_id=order.id,
    )


@login_required
@require_POST
def order_item_delete(request, order_id, item_id):
    if not user_can_operate_sales(request.user):
        raise PermissionDenied(
            "Tu rol no permite modificar pedidos."
        )

    order = get_order_for_user_or_404(
        request.user,
        order_id,
    )

    item = get_object_or_404(
        OrderItem,
        id=item_id,
        order=order,
    )

    if not order.can_be_edited:
        messages.error(
            request,
            "Solo puedes eliminar ítems de pedidos abiertos.",
        )
        return redirect(
            "sales:order_detail",
            order_id=order.id,
        )

    item_description = (
        f"{item.quantity} × {item.dish_name}"
    )

    with transaction.atomic():
        item.delete()

        log_action(
            request,
            action=AuditLog.Action.DELETE,
            module="sales",
            venue=order.service_session.table.venue,
            object_type="OrderItem",
            object_id=item_id,
            description=(
                f"Eliminó {item_description} "
                f"del pedido #{order.id}."
            ),
        )

    messages.success(
        request,
        f"Se eliminó {item_description}.",
    )

    return redirect(
        "sales:order_detail",
        order_id=order.id,
    )


@login_required
@require_POST
def order_discount_update(request, order_id):
    if not user_can_operate_sales(request.user):
        raise PermissionDenied(
            "Tu rol no permite aplicar descuentos."
        )

    order = get_order_for_user_or_404(
        request.user,
        order_id,
    )

    if not order.can_be_edited:
        messages.error(
            request,
            "Solo puedes modificar descuentos en pedidos abiertos.",
        )
        return redirect(
            "sales:order_detail",
            order_id=order.id,
        )

    form = OrderDiscountForm(
        request.POST,
        instance=order,
    )

    if form.is_valid():
        with transaction.atomic():
            updated_order = form.save(commit=False)
            updated_order.save(
                update_fields=(
                    "discount_amount",
                    "updated_at",
                )
            )
            updated_order.recalculate_totals()

            log_action(
                request,
                action=AuditLog.Action.UPDATE,
                module="sales",
                venue=updated_order.service_session.table.venue,
                object_type="Order",
                object_id=updated_order.id,
                description=(
                    f"Actualizó el descuento del pedido "
                    f"#{updated_order.id} a "
                    f"${updated_order.discount_amount}."
                ),
            )

        messages.success(
            request,
            "Descuento actualizado correctamente.",
        )

    else:
        messages.error(
            request,
            "No se pudo actualizar el descuento. "
            + " ".join(e for errs in form.errors.values() for e in errs),
        )

    return redirect(
        "sales:order_detail",
        order_id=order.id,
    )


@login_required
@require_POST
def order_confirm(request, order_id):
    if not user_can_operate_sales(request.user):
        raise PermissionDenied(
            "Tu rol no permite confirmar pedidos."
        )

    order = get_order_for_user_or_404(
        request.user,
        order_id,
    )

    try:
        with transaction.atomic():
            order.confirm()

            log_action(
                request,
                action=AuditLog.Action.UPDATE,
                module="sales",
                venue=order.service_session.table.venue,
                object_type="Order",
                object_id=order.id,
                description=(
                    f"Confirmó el pedido #{order.id} "
                    f"por ${order.total}."
                ),
            )

        messages.success(
            request,
            f"Pedido #{order.id} confirmado.",
        )

    except ValidationError as error:
        messages.error(request, error.messages[0])

    return redirect(
        "sales:order_detail",
        order_id=order.id,
    )


@login_required
@require_POST
def order_pay(request, order_id):
    if not user_can_operate_sales(request.user):
        raise PermissionDenied(
            "Tu rol no permite registrar pagos."
        )

    order = get_order_for_user_or_404(
        request.user,
        order_id,
    )

    form = PaymentForm(request.POST)

    if not form.is_valid():
        messages.error(
            request,
            "Selecciona un medio de pago válido.",
        )
        return redirect(
            "sales:order_detail",
            order_id=order.id,
        )

    try:
        with transaction.atomic():
            order.mark_as_paid(
                form.cleaned_data["payment_method"]
            )

            log_action(
                request,
                action=AuditLog.Action.UPDATE,
                module="sales",
                venue=order.service_session.table.venue,
                object_type="Order",
                object_id=order.id,
                description=(
                    f"Registró el pago del pedido #{order.id} "
                    f"por ${order.total} mediante "
                    f"{order.get_payment_method_display()}."
                ),
            )

        messages.success(
            request,
            f"Pago del pedido #{order.id} registrado.",
        )

    except ValidationError as error:
        messages.error(request, error.messages[0])

    return redirect(
        "sales:order_detail",
        order_id=order.id,
    )


@login_required
@require_POST
def order_cancel(request, order_id):
    if not user_can_operate_sales(request.user):
        raise PermissionDenied(
            "Tu rol no permite anular pedidos."
        )

    order = get_order_for_user_or_404(
        request.user,
        order_id,
    )

    try:
        with transaction.atomic():
            order.cancel()

            log_action(
                request,
                action=AuditLog.Action.UPDATE,
                module="sales",
                venue=order.service_session.table.venue,
                object_type="Order",
                object_id=order.id,
                description=(
                    f"Anuló el pedido #{order.id}."
                ),
            )

        messages.success(
            request,
            f"Pedido #{order.id} anulado.",
        )

    except ValidationError as error:
        messages.error(request, error.messages[0])

    return redirect(
        "sales:order_detail",
        order_id=order.id,
    )