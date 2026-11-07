from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from analytics.views import get_accessible_venues
from authentication.permissions import get_or_create_profile

from .models import Notification
from .services.notifications import active_for, generate, kinds_for, serialize


def _scope(request):
    profile = get_or_create_profile(request.user)
    return profile, get_accessible_venues(profile)


@login_required
def feed(request):
    profile, venues = _scope(request)
    if kinds_for(profile):
        generate(venues)
    items = [serialize(n) for n in active_for(profile, venues)]
    return JsonResponse({"count": len(items), "items": items})


@login_required
@require_POST
def acknowledge(request, pk):
    profile, venues = _scope(request)
    notification = get_object_or_404(Notification, pk=pk, venue__in=venues)
    if notification.acknowledged_at is None:
        notification.acknowledged_at, notification.acknowledged_by = timezone.now(), request.user
        notification.save(update_fields=["acknowledged_at", "acknowledged_by"])
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"ok": True})
    return redirect("waiter:home")


def _waiter_context(request):
    from .services.floor import build_floor

    profile, venues = _scope(request)
    if kinds_for(profile):
        generate(venues)
    floor = build_floor(venues)
    cards = [card for _, zone_cards in floor["zones"] for card in zone_cards]
    from authentication.zones import user_zones, zone_ok

    zones = user_zones(profile)
    cards = [card for card in cards if zone_ok(zones, card["table"].zone_name)]
    recent = (Notification.objects.filter(venue__in=venues, acknowledged_at__gte=timezone.now() - timedelta(minutes=10))
              .select_related("acknowledged_by", "table")[:5])
    return {"alerts": [serialize(n) for n in active_for(profile, venues)], "cards": cards,
            "counts": floor["counts"], "waitlist": floor["waitlist"], "recent": recent}


@login_required
def waiter_home(request):
    return render(request, "operations/waiter.html", _waiter_context(request))


@login_required
def waiter_panel(request):
    return render(request, "operations/_waiter_panel.html", _waiter_context(request))
