from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from analytics.views import get_accessible_venues
from authentication.models import Profile
from authentication.permissions import get_or_create_profile

from .services.kitchen import BAR, KITCHEN, acceptance, advance, queue


def _station(request):
    return BAR if request.resolver_match.namespace == "bar" else KITCHEN


def _context(request):
    namespace = request.resolver_match.namespace
    station = _station(request)
    venues = get_accessible_venues(get_or_create_profile(request.user))
    return venues, {**queue(venues, station), "board_url": reverse(f"{namespace}:board"),
                    "advance_url": reverse(f"{namespace}:advance")}


@login_required
def station_view(request):
    venues, context = _context(request)
    context["acceptance"] = acceptance(venues, context["station"])
    return render(request, "sales/kds.html", context)


@login_required
def station_board(request):
    return render(request, "sales/_kds_board.html", _context(request)[1])


@login_required
@require_POST
def station_advance(request):
    if get_or_create_profile(request.user).role == Profile.Role.VIEWER:
        raise PermissionDenied("Tu rol no puede modificar las comandas.")
    venues, _ = _context(request)
    ids = [int(value) for value in request.POST.get("ids", "").split(",") if value.strip().isdigit()]
    advance(ids, venues, _station(request))
    return redirect(f"{request.resolver_match.namespace}:home")
