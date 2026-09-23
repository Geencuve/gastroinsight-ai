from authentication.permissions import get_or_create_profile


def get_accessible_venues(user):
    profile = get_or_create_profile(user)

    if profile.is_platform_admin:
        from venues.models import Venue

        return Venue.objects.filter(is_active=True)

    return profile.venues.filter(is_active=True)