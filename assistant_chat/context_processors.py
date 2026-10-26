from django.db.models import Q

from authentication.models import Profile


def assistant_widget_access(request):
    user = request.user

    if not user.is_authenticated:
        return {"show_staff_assistant_widget": False}

    if user.is_superuser:
        return {"show_staff_assistant_widget": True}

    has_access = Profile.objects.filter(user=user).filter(
        Q(role=Profile.Role.PLATFORM_ADMIN)
        | Q(venues__is_active=True)
    ).exists()

    return {"show_staff_assistant_widget": has_access}