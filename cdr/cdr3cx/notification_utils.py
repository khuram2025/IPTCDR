"""Resolve notification recipients for quota and billing alerts."""
from django.conf import settings


def resolve_extension_alert_email(extension):
    """Return the best email for an extension's quota/billing alerts."""
    if extension.email:
        return extension.email

    from accounts.models import CustomUser

    company = extension.company
    if company:
        admin = (
            CustomUser.objects.filter(company=company, role='company_admin', is_active=True)
            .exclude(email='')
            .order_by('id')
            .first()
        )
        if admin and admin.email:
            return admin.email

    fallback = getattr(settings, 'QUOTA_ALERT_FALLBACK_EMAIL', None)
    if fallback:
        return fallback

    return settings.DEFAULT_FROM_EMAIL
