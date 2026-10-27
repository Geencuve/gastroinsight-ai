from django.contrib import admin

from .models import Dish, Menu


class DishInline(admin.TabularInline):
    model = Dish
    extra = 1
    fields = ("name", "category", "price", "is_available", "image")


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ("name", "venue", "is_active", "created_at")
    list_filter = ("is_active", "venue")
    search_fields = ("name", "venue__name")
    inlines = [DishInline]


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("name", "menu", "category", "price", "is_available")
    list_filter = ("category", "is_available", "menu__venue")
    search_fields = ("name", "menu__name", "menu__venue__name")