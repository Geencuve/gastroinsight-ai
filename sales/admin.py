from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    readonly_fields = (
        "dish_name",
        "unit_price",
        "line_total",
        "created_at",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "service_session",
        "status",
        "subtotal",
        "discount_amount",
        "total",
        "payment_method",
        "opened_at",
        "created_by",
    )
    list_filter = (
        "status",
        "payment_method",
        "service_session__table__venue",
    )
    search_fields = (
        "service_session__table__code",
        "service_session__table__venue__name",
    )
    readonly_fields = (
        "opened_at",
        "confirmed_at",
        "paid_at",
        "cancelled_at",
        "subtotal",
        "total",
        "updated_at",
    )
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "dish_name",
        "quantity",
        "unit_price",
        "line_total",
    )
    list_filter = (
        "order__status",
        "order__service_session__table__venue",
    )
    search_fields = (
        "dish_name",
        "order__service_session__table__code",
    )
    readonly_fields = (
        "dish_name",
        "unit_price",
        "line_total",
        "created_at",
    )