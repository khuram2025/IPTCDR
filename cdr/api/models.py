"""API key + webhook subscription models."""
import secrets
import hashlib

from django.conf import settings
from django.db import models
from django.utils import timezone


def _make_key() -> str:
    """Generate a 40-char URL-safe API key."""
    return secrets.token_urlsafe(30)[:40]


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode('utf-8')).hexdigest()


class ApiKey(models.Model):
    """Per-tenant API key.

    The clear-text value is shown ONCE on creation; only the SHA-256 hash is
    stored. Keys are scoped to a Company; rate-limit tier controls throttling.
    """

    TIER_CHOICES = [
        ('free', 'Free (60 req/min)'),
        ('paid', 'Paid (600 req/min)'),
        ('pro',  'Pro (6000 req/min)'),
    ]

    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='api_keys',
    )
    name = models.CharField(max_length=128, help_text="Human label, e.g. 'Power BI integration'")
    key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    key_prefix = models.CharField(max_length=8, db_index=True,
                                  help_text="First 8 chars of the key for identification")
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default='paid')
    scopes = models.JSONField(default=list, blank=True,
                              help_text="Restrict to ['read:cdr', 'write:extension', ...]")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['key_prefix']),
        ]

    def __str__(self):
        return f"{self.company.name}/{self.name} ({self.key_prefix}…)"

    @classmethod
    def generate(cls, company, name, **kwargs):
        """Create an API key. Returns ``(api_key_obj, plaintext_key)``.

        The plaintext is only available at creation time — store/show it once.
        """
        plaintext = _make_key()
        obj = cls.objects.create(
            company=company,
            name=name,
            key_hash=_hash_key(plaintext),
            key_prefix=plaintext[:8],
            **kwargs,
        )
        return obj, plaintext

    @classmethod
    def lookup(cls, plaintext: str):
        """Resolve a plaintext key to its ApiKey row, or None."""
        try:
            return cls.objects.select_related('company').get(
                key_hash=_hash_key(plaintext), is_active=True,
            )
        except cls.DoesNotExist:
            return None

    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at < timezone.now())

    def touch(self):
        """Update last_used_at without triggering save signals."""
        type(self).objects.filter(pk=self.pk).update(last_used_at=timezone.now())


# ---------------------------------------------------------------------------
# Webhook subscriptions (outbound)
# ---------------------------------------------------------------------------


class WebhookSubscription(models.Model):
    """Tenant-registered webhook URL subscribed to specific event types."""

    EVENT_CHOICES = [
        ('call.completed',     'Call completed'),
        ('call.missed',        'Call missed'),
        ('call.cost_recorded', 'Call cost recorded'),
        ('quota.threshold',    'Quota threshold reached'),
        ('quota.exceeded',     'Quota exceeded'),
        ('fraud.detected',     'Fraud incident detected'),
        ('fraud.acknowledged', 'Fraud incident acknowledged'),
        ('extension.disabled', 'Extension auto-disabled'),
        ('invoice.issued',     'Invoice issued'),
        ('invoice.paid',       'Invoice paid'),
        ('invoice.failed',     'Invoice payment failed'),
    ]

    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='webhook_subscriptions',
    )
    name = models.CharField(max_length=128)
    url = models.URLField(max_length=512)
    events = models.JSONField(default=list,
                              help_text="Subscribed event types — see WebhookSubscription.EVENT_CHOICES")
    secret = models.CharField(max_length=64,
                              help_text="Used to sign payloads (HMAC-SHA256)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_failure_at = models.DateTimeField(null=True, blank=True)
    consecutive_failures = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'is_active'])]

    def __str__(self):
        return f"{self.company.name}/{self.name} -> {self.url}"

    @classmethod
    def generate_secret(cls) -> str:
        return secrets.token_urlsafe(32)


class WebhookDelivery(models.Model):
    """Outbound delivery attempt log."""

    STATUS = [
        ('pending',   'Pending'),
        ('delivered', 'Delivered'),
        ('failed',    'Failed (retries exhausted)'),
        ('giving_up', 'Dead-letter'),
    ]

    subscription = models.ForeignKey(WebhookSubscription, on_delete=models.CASCADE,
                                     related_name='deliveries')
    event_type = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS, default='pending', db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    last_status_code = models.IntegerField(null=True, blank=True)
    last_response_excerpt = models.CharField(max_length=512, blank=True, default='')
    next_retry_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'next_retry_at']),
            models.Index(fields=['subscription', '-created_at']),
        ]

    def __str__(self):
        return f"{self.event_type} -> {self.subscription} ({self.status})"
