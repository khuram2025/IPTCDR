from django.db import models
from django.utils import timezone

class Notification(models.Model):
    recipient = models.EmailField()  # Recipient email address
    subject = models.CharField(max_length=255)
    message = models.TextField()
    sent_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Notification to {self.recipient}"


# ---------------------------------------------------------------------------
# P4.4 — Tenant-configurable alert rules engine
# ---------------------------------------------------------------------------
class AlertRule(models.Model):
    """A tenant-configurable rule that turns an event source (fraud incidents, ACD
    SLA breaches, quota exhaustion) into multi-channel alerts with optional
    time-based escalation. Generalises the ACD-only ThresholdPolicy (P2.3/P2.6).
    Nothing fires until a rule exists — safe by default."""
    SOURCE_FRAUD = 'fraud'
    SOURCE_ACD_SLA = 'acd_sla'
    SOURCE_QUOTA = 'quota'
    SOURCE_SURVEY_CSAT = 'survey_csat'
    SOURCE_CHOICES = [
        (SOURCE_FRAUD, 'Fraud incidents'),
        (SOURCE_ACD_SLA, 'ACD SLA breaches'),
        (SOURCE_QUOTA, 'Quota exhaustion'),
        (SOURCE_SURVEY_CSAT, 'Survey CSAT below target'),
    ]
    SEVERITY_ORDER = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4,
                      'amber': 2, 'red': 3}

    company = models.ForeignKey(
        'accounts.Company', null=True, blank=True, on_delete=models.CASCADE,
        related_name='alert_rules', help_text='Null = applies to all tenants')
    name = models.CharField(max_length=120)
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES)
    min_severity = models.CharField(
        max_length=10, default='high',
        help_text='low/medium/high/critical (fraud) or amber/red (ACD)')
    channels = models.CharField(
        max_length=80, default='email',
        help_text='Comma list: email, sms, whatsapp')
    recipients = models.TextField(help_text='Emails / phone numbers, comma separated')
    escalate_after_minutes = models.PositiveIntegerField(
        default=0, help_text='0 = no escalation')
    escalate_recipients = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['company', 'source', 'name']

    def __str__(self):
        scope = self.company.name if self.company_id else 'ALL'
        return f"{self.name} [{scope}/{self.source}]"

    def channel_list(self):
        return [c.strip().lower() for c in (self.channels or '').split(',') if c.strip()]

    def recipient_list(self, escalation=False):
        import re
        raw = self.escalate_recipients if escalation else self.recipients
        return [r.strip() for r in re.split(r'[,;\n]+', raw or '') if r.strip()]

    def severity_ge(self, severity):
        want = self.SEVERITY_ORDER.get((self.min_severity or '').lower(), 99)
        got = self.SEVERITY_ORDER.get((severity or '').lower(), 0)
        return got >= want


class AlertEvent(models.Model):
    """Audit of one dispatched alert (and whether it later escalated)."""
    rule = models.ForeignKey(AlertRule, null=True, on_delete=models.SET_NULL,
                             related_name='events')
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE,
                                related_name='alert_events')
    source = models.CharField(max_length=16)
    severity = models.CharField(max_length=10, blank=True, default='')
    summary = models.CharField(max_length=255)
    reference = models.CharField(max_length=64, blank=True, default='',
                                 help_text='Source object id (e.g. FraudIncident pk)')
    channels_sent = models.CharField(max_length=80, blank=True, default='')
    delivered = models.BooleanField(default=False)
    escalated = models.BooleanField(default=False)
    escalated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', '-created_at']),
                   models.Index(fields=['source', 'escalated'])]

    def __str__(self):
        return f"{self.source} alert: {self.summary[:48]}"
