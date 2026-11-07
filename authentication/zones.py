"""Zonas asignadas a cada usuario: limitan las mesas, alertas y cámaras que ve."""


def user_zones(profile):
    if profile.is_platform_admin or profile.user.is_superuser:
        return None
    zones = {zone.strip().lower() for zone in (getattr(profile, "zones", "") or "").split(",") if zone.strip()}
    return zones or None


def zone_ok(zones, zone_name):
    return zones is None or (zone_name or "").strip().lower() in zones
