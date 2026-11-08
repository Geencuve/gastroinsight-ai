"""Opiniones de clientes mediante un código QR por mesa (sin cuenta)."""
from datetime import timedelta

import segno
from django import forms
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from analytics.views import get_accessible_venues
from authentication.permissions import get_or_create_profile
from menus.models import Dish

from .models import RestaurantTable, SatisfactionEvaluation, ServiceSession

SIGNER = signing.Signer(salt="gastroinsight-feedback")
MAX_PER_SESSION = 10
RECENT_HOURS = 3


def table_token(table):
    return SIGNER.sign(str(table.id))


def table_from_token(token):
    try:
        table_id = int(SIGNER.unsign(token))
    except (signing.BadSignature, ValueError):
        raise Http404("Código QR no válido.")
    return get_object_or_404(
        RestaurantTable.objects.select_related("venue"), id=table_id, is_active=True, venue__is_active=True,
    )


def feedback_session(table):
    """Atención abierta de la mesa o, si no hay, la cerrada en las últimas horas."""
    current = ServiceSession.objects.filter(
        table=table, status=ServiceSession.Status.OPEN,
    ).order_by("-started_at").first()
    if current:
        return current
    return ServiceSession.objects.filter(
        table=table, status=ServiceSession.Status.CLOSED,
        ended_at__gte=timezone.now() - timedelta(hours=RECENT_HOURS),
    ).order_by("-ended_at").first()


class CustomerFeedbackForm(forms.Form):
    rating = forms.TypedChoiceField(
        choices=[(value, str(value)) for value in range(5, 0, -1)],
        coerce=int, widget=forms.RadioSelect, label="¿Cómo fue tu experiencia?",
    )
    dish = forms.ModelChoiceField(
        queryset=Dish.objects.none(), required=False,
        label="¿Quieres calificar un plato en particular?", empty_label="Experiencia general",
    )
    comment = forms.CharField(
        required=False, max_length=500, label="Comentario (opcional)",
        widget=forms.Textarea(attrs={
            "rows": 3, "placeholder": "Cuéntanos qué te gustó o qué podemos mejorar.",
        }),
    )

    def __init__(self, *args, session=None, **kwargs):
        super().__init__(*args, **kwargs)
        dishes = Dish.objects.none()
        if session is not None:
            dishes = Dish.objects.filter(order_items__order__service_session=session).distinct()
            if not dishes.exists():
                dishes = Dish.objects.filter(
                    menu__venue=session.table.venue, menu__is_active=True, is_available=True,
                )
        self.fields["dish"].queryset = dishes.order_by("category", "name")


def customer_feedback(request, token):
    table = table_from_token(token)
    session = feedback_session(table)
    context = {
        "table": table,
        "venue": table.venue,
        "menu_url": reverse("menus:public", args=[table.venue_id]),
    }
    if session is None:
        return render(request, "operations/feedback_form.html", {**context, "no_session": True})

    session_key = f"gi_feedback_{session.id}"
    if request.session.get(session_key):
        return redirect("feedback:thanks", token=token)

    form = CustomerFeedbackForm(request.POST or None, session=session)
    if request.method == "POST" and form.is_valid():
        received = session.evaluations.filter(source=SatisfactionEvaluation.Source.CUSTOMER_QR).count()
        if received >= MAX_PER_SESSION:
            form.add_error(None, "Esta mesa ya alcanzó el máximo de opiniones para esta atención.")
        else:
            evaluation = SatisfactionEvaluation(
                service_session=session,
                dish=form.cleaned_data["dish"],
                rating=form.cleaned_data["rating"],
                comment=form.cleaned_data["comment"].strip(),
                source=SatisfactionEvaluation.Source.CUSTOMER_QR,
            )
            try:
                evaluation.full_clean()
            except ValidationError as error:
                form.add_error(None, " ".join(error.messages))
            else:
                evaluation.save()
                request.session[session_key] = True
                return redirect("feedback:thanks", token=token)

    return render(request, "operations/feedback_form.html", {**context, "form": form})


def feedback_thanks(request, token):
    table = table_from_token(token)
    return render(request, "operations/feedback_thanks.html", {
        "table": table,
        "venue": table.venue,
        "menu_url": reverse("menus:public", args=[table.venue_id]),
        "chat_url": reverse("assistant_chat:customer_chat", args=[table.venue_id]),
    })


@login_required
def table_qr_codes(request):
    profile = get_or_create_profile(request.user)
    venues = get_accessible_venues(profile)
    cards = []
    for table in RestaurantTable.objects.filter(venue__in=venues, is_active=True).select_related("venue").order_by("venue__name", "code"):
        url = request.build_absolute_uri(reverse("feedback:form", args=[table_token(table)]))
        svg = segno.make(url, error="m").svg_inline(omitsize=True, scale=4, border=2, dark="#05070b", light="#ffffff")
        cards.append({"table": table, "url": url, "svg": mark_safe(svg)})  # nosec B308 B703 - SVG del QR generado por el propio sistema, sin datos del usuario
    return render(request, "operations/feedback_qr.html", {"cards": cards})
