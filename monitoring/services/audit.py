from monitoring.models import AuditLog


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def log_action(
    request,
    *,
    action,
    module,
    description,
    venue=None,
    object_type="",
    object_id="",
):
    user = (
        request.user
        if getattr(request, "user", None)
        and request.user.is_authenticated
        else None
    )

    return AuditLog.objects.create(
        user=user,
        venue=venue,
        action=action,
        module=module,
        object_type=object_type,
        object_id=str(object_id) if object_id else "",
        description=description[:255],
        ip_address=get_client_ip(request),
    )