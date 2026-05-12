"""Security & compliance models.

- AuditLogEntry: who did what, when, from where
- CompanyIpWhitelist: allowed CIDRs per tenant (admin can override)
- CompanySecurityPolicy: per-tenant session timeout + password rules
- PasswordHistory: prevent reuse (validator)
"""
import ipaddress

from django.conf import settings
from django.db import models


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class AuditLogEntry(models.Model):
    """One row per state-changing HTTP request (POST/PUT/PATCH/DELETE)."""

    company = models.ForeignKey(
        'accounts.Company', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_log_entries', db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_log_entries', db_index=True,
    )
    user_email = models.CharField(max_length=255, blank=True, default='',
                                  help_text="Snapshot of email at action time")
    method = models.CharField(max_length=8, db_index=True)
    path = models.CharField(max_length=512, db_index=True)
    status_code = models.IntegerField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    user_agent = models.CharField(max_length=512, blank=True, default='')
    object_repr = models.CharField(max_length=255, blank=True, default='',
                                   help_text="Short label for the affected object")
    extra = models.JSONField(default=dict, blank=True,
                             help_text="Diff or context payload")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', '-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.user_email} {self.method} {self.path}"


# ---------------------------------------------------------------------------
# IP whitelist
# ---------------------------------------------------------------------------


class CompanyIpWhitelist(models.Model):
    """Per-tenant CIDR allow-list. If empty for a company, all IPs are allowed."""

    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='ip_whitelist_entries',
    )
    cidr = models.CharField(max_length=43,
                            help_text="IP or CIDR (e.g. 203.0.113.5 or 203.0.113.0/24)")
    label = models.CharField(max_length=128, blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['company', 'cidr']
        unique_together = [('company', 'cidr')]

    def __str__(self):
        return f"{self.company.name}: {self.cidr} ({self.label})"

    def matches(self, ip_str: str) -> bool:
        try:
            net = ipaddress.ip_network(self.cidr, strict=False)
            return ipaddress.ip_address(ip_str) in net
        except ValueError:
            return False


# ---------------------------------------------------------------------------
# Per-tenant security policy
# ---------------------------------------------------------------------------


class CompanySecurityPolicy(models.Model):
    """One row per Company. Created lazily on first access."""

    company = models.OneToOneField(
        'accounts.Company', on_delete=models.CASCADE, related_name='security_policy',
    )
    session_timeout_minutes = models.PositiveIntegerField(
        default=480, help_text="Idle timeout for portal sessions (default 8h)",
    )
    enforce_ip_whitelist = models.BooleanField(
        default=False,
        help_text="If true and any whitelist entries exist, non-listed IPs are blocked.",
    )
    require_strong_password = models.BooleanField(
        default=True, help_text="Min length 12 + complexity rules",
    )
    password_history_size = models.PositiveSmallIntegerField(
        default=5, help_text="Block reuse of last N passwords",
    )
    password_max_age_days = models.PositiveSmallIntegerField(
        default=0, help_text="0 = no expiry; otherwise force reset after N days",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Company security policies"

    def __str__(self):
        return f"Policy({self.company.name})"

    @classmethod
    def for_company(cls, company):
        if company is None:
            return None
        obj, _ = cls.objects.get_or_create(company=company)
        return obj


# ---------------------------------------------------------------------------
# Password history (for re-use prevention)
# ---------------------------------------------------------------------------


class PasswordHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='password_history',
    )
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', '-created_at'])]
