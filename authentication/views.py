from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from monitoring.models import AuditLog
from monitoring.services.audit import log_action
from .forms import LoginForm, RegisterForm
from .models import Profile


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
    profile, created = Profile.objects.get_or_create(
    user=request.user
)

    return render(
        request,
        "authentication/profile.html",
        {"profile": profile},
    )