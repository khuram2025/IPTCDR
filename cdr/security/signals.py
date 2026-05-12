"""Track password changes so the history validator can prevent reuse."""
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import PasswordHistory


@receiver(pre_save, sender='accounts.CustomUser')
def _record_password_change(sender, instance, **kwargs):
    """If the password hash changed, snapshot it into PasswordHistory.

    Runs on user save so password resets, admin changes, and self-service
    changes are all captured.
    """
    if not instance.pk:
        return  # new user — no prior to record
    try:
        previous = sender.objects.only('password').get(pk=instance.pk).password
    except sender.DoesNotExist:
        return
    if previous and previous != instance.password:
        PasswordHistory.objects.create(user_id=instance.pk, password_hash=previous)


@receiver(user_logged_in)
def _audit_login(sender, user, request, **kwargs):
    """Also log successful logins as audit events (POST /accounts/login/ already
    captures this, but logging here ensures non-form login paths are traced too).
    """
    from .middleware import _client_ip
    from .models import AuditLogEntry
    AuditLogEntry.objects.create(
        company=getattr(user, 'company', None),
        user=user,
        user_email=getattr(user, 'email', '') or '',
        method='LOGIN',
        path=request.path[:512] if request else '',
        status_code=200,
        ip=_client_ip(request) if request else None,
        user_agent=(request.META.get('HTTP_USER_AGENT', '') if request else '')[:512],
        object_repr='LOGIN_SUCCESS',
    )
