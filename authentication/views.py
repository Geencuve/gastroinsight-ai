from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from monitoring.models import AuditLog
from monitoring.services.audit import log_action
from venues.models import Venue

from .forms import AccountForm, LoginForm, RegisterForm
from .models import Profile

ALL_ROLES = {"platform_admin", "venue_admin", "operator", "viewer"}
OPERATORS = {"platform_admin", "venue_admin", "operator"}
MANAGERS = {"platform_admin", "venue_admin"}
CAPABILITIES = [
    ("Ver inicio, dashboard, reportes y correlación", ALL_ROLES),
    ("Operar mesas, pedidos, pagos y evaluaciones", OPERATORS),
    ("Iniciar análisis visual y el monitor en vivo", OPERATORS),
    ("Gestionar mesas, carta y fotos de platos", MANAGERS),
    ("Editar políticas de privacidad", MANAGERS),
    ("Ver auditoría y administrar la plataforma", {"platform_admin"}),
]


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    form = LoginForm(
        request,
        data=request.POST or None,
    )

    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        log_action(request,action=AuditLog.Action.LOGIN,module="authentication",description=(f"Inicio de sesión de " f"{request.user.get_username()}."),
)
        messages.success(
            request, f"Bienvenido/a, {request.user.get_username()}.",
        )
        return redirect("core:home")

    return render(request,"authentication/login.html",{"form": form},
    )


def register_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    form = RegisterForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()

        login(request, user)

        messages.success(
            request,
            "Tu cuenta fue creada correctamente. "
            "Un administrador debe asignarte un rol y locales.",
        )

        return redirect("core:home")

    return render(
        request,
        "authentication/register.html",
        {"form": form},
    )


@require_POST
@login_required
def logout_view(request):
    log_action(
    request,
    action=AuditLog.Action.LOGOUT,
    module="authentication",
    description=(
        f"Cierre de sesión de "
        f"{request.user.get_username()}."
    ),
)
    logout(request)
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect("authentication:login")


@login_required
def profile_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    form = AccountForm(request.POST or None, instance=request.user, profile=profile)

    if request.method == "POST" and form.is_valid():
        form.save()
        log_action(
            request, action=AuditLog.Action.UPDATE, module="authentication",
            description=f"Actualizó los datos de su cuenta ({request.user.get_username()}).",
        )
        messages.success(request, "Tus datos se actualizaron correctamente.")
        return redirect(reverse("authentication:profile") + "#configuracion")

    role_key = "platform_admin" if profile.is_platform_admin else profile.role
    capabilities = [
        {"label": label, "allowed": role_key in roles} for label, roles in CAPABILITIES
    ]

    time_field = next(
        (f.name for f in AuditLog._meta.fields if f.get_internal_type() == "DateTimeField"), None,
    )
    logs = AuditLog.objects.filter(user=request.user).order_by(f"-{time_field}" if time_field else "-id")[:8]
    activity = [
        {
            "action": log.get_action_display(),
            "module": log.module,
            "description": log.description,
            "when": getattr(log, time_field) if time_field else None,
        }
        for log in logs
    ]

    name = request.user.first_name or request.user.username
    venues = Venue.objects.filter(is_active=True) if profile.is_platform_admin else profile.venues.all()
    return render(request, "authentication/profile.html", {
        "profile": profile,
        "form": form,
        "initial": name[:1].upper(),
        "role_key": role_key,
        "capabilities": capabilities,
        "venues": venues,
        "all_venues": profile.is_platform_admin,
        "activity": activity,
    })
