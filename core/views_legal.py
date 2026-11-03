from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from monitoring.models import AuditLog
from monitoring.services.audit import log_action

from .legal import ADVISOR, COURSE, LEGAL_DATE, LEGAL_VERSION, LICENSES, PAGES, TEAM, URL_NAMES
from .models import LegalAcceptance


def _context():
    return {"version": LEGAL_VERSION, "date": LEGAL_DATE, "team": TEAM, "advisor": ADVISOR, "course": COURSE,
            "licenses": LICENSES, "contact_email": getattr(settings, "CONTACT_EMAIL", "")}


def legal_page(request, slug):
    if slug not in PAGES:
        raise Http404
    title, template = PAGES[slug]
    nav = [{"title": t, "url": reverse(f"core:{URL_NAMES[s]}"), "active": s == slug} for s, (t, _) in PAGES.items()]
    return render(request, "core/legal/page.html", {"title": title, "body_template": template, "nav": nav,
                                                     "legal": _context()})


class AcceptanceForm(forms.Form):
    educational = forms.BooleanField(
        label="Entiendo que GastroInsight AI es un prototipo académico y lo usaré solo con fines educativos.")
    terms = forms.BooleanField(
        label="He leído y acepto los Términos y condiciones y la Política de privacidad.")
    responsible = forms.BooleanField(
        label="Me comprometo a no usar el sistema para identificar, vigilar o evaluar a personas en particular.")
    full_name = forms.CharField(label="Escribe tu nombre completo como firma", max_length=150)


@login_required
def acceptance(request):
    next_url = request.POST.get("next") or request.GET.get("next") or "/"
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = "/"
    if LegalAcceptance.objects.filter(user=request.user, version=LEGAL_VERSION).exists():
        request.session[f"legal_ok_{LEGAL_VERSION}"] = True
        return redirect(next_url)

    form = AcceptanceForm(request.POST or None, initial={"full_name": request.user.get_full_name()})
    if request.method == "POST" and form.is_valid():
        LegalAcceptance.objects.create(
            user=request.user, version=LEGAL_VERSION, full_name=form.cleaned_data["full_name"].strip(),
            ip_address=request.META.get("REMOTE_ADDR") or None,
            user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:255],
        )
        request.session[f"legal_ok_{LEGAL_VERSION}"] = True
        log_action(request, action=AuditLog.Action.CREATE, module="core", object_type="LegalAcceptance",
                   object_id=LEGAL_VERSION,
                   description=f"Aceptó la toma de conocimiento de uso educativo v{LEGAL_VERSION}.")
        return redirect(next_url)
    return render(request, "core/legal/acceptance.html", {"form": form, "next": next_url, "legal": _context()})
