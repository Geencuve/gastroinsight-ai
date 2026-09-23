from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import OrderItem


@receiver(post_save, sender=OrderItem)
def recalculate_order_after_item_save(sender, instance, **kwargs):
    instance.order.recalculate_totals()


@receiver(post_delete, sender=OrderItem)
def recalculate_order_after_item_delete(sender, instance, **kwargs):
    instance.order.recalculate_totals()