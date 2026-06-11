"""Billing models — tax engine, invoices, payments, fraud rules.

Phase 1 ships TaxRule + FraudRule + FraudIncident. Invoices and payment
gateway records will land in subsequent migrations once gateway integration
work begins.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------------------
# Tax engine
# ---------------------------------------------------------------------------


class TaxRule(models.Model):
    """Country-level VAT/tax rate, optionally overridable per company."""

    APPLIES_TO_CHOICES = [
        ('SUBSCRIPTION', 'Subscription only'),
        ('USAGE', 'Usage only'),
        ('BOTH', 'Subscription + Usage'),
    ]

    name = models.CharField(max_length=64,
                            help_text="e.g. 'KSA VAT 15%', 'UAE VAT 5%'")
    country_code = models.CharField(max_length=2, db_index=True,
                                    help_text="ISO 3166-1 alpha-2 (SA, AE, EG…)")
    rate_percent = models.DecimalField(max_digits=5, decimal_places=2,
                                       help_text="e.g. 15.00 for 15%")
    applies_to = models.CharField(max_length=20, choices=APPLIES_TO_CHOICES, default='BOTH')
    effective_from = models.DateField(default=timezone.now)
    effective_to = models.DateField(null=True, blank=True)
    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='tax_rules',
        help_text="If set, overrides country default for this tenant only",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['country_code', '-effective_from']
        indexes = [models.Index(fields=['country_code', 'is_active'])]

    def __str__(self):
        scope = f" [tenant: {self.company.name}]" if self.company_id else ""
        return f"{self.name} ({self.rate_percent}%){scope}"

    def calculate(self, subtotal: Decimal) -> Decimal:
        return (subtotal * self.rate_percent / Decimal('100')).quantize(Decimal('0.01'))


# ---------------------------------------------------------------------------
# Toll-fraud detection (P1-057 → P1-063)
# ---------------------------------------------------------------------------


class FraudRule(models.Model):
    """Declarative rule evaluated against incoming CDRs to detect toll fraud."""

    RULE_TYPES = [
        ('intl_spike',          'International call spike'),
        ('after_hours_intl',    'After-hours international'),
        ('premium_destination', 'Premium-rate destination'),
        ('blacklist_country',   'Blacklisted country'),
        ('velocity_calls',      'Velocity — calls per minute'),
        ('velocity_cost',       'Velocity — cost per hour'),
        ('velocity_duration',   'Velocity — duration per day'),
        ('new_destination',     'First call to a country'),
        ('long_intl',           'Long international call'),
        ('concurrent_calls',    'Concurrent calls per extension'),
    ]
    SEVERITY = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')]
    ACTIONS = [
        ('alert',             'Alert only'),
        ('disable_extension', 'Auto-disable extension'),
        ('block_route',       'Block route at SBC'),
    ]

    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='fraud_rules',
    )
    name = models.CharField(max_length=128)
    rule_type = models.CharField(max_length=32, choices=RULE_TYPES)
    threshold = models.DecimalField(max_digits=12, decimal_places=2,
                                    help_text="Numeric threshold meaning depends on rule_type")
    time_window_minutes = models.PositiveIntegerField(default=60,
                                                      help_text="Evaluation window in minutes")
    countries = models.JSONField(default=list, blank=True,
                                 help_text="ISO country codes (for blacklist / premium rules)")
    severity = models.CharField(max_length=10, choices=SEVERITY, default='medium')
    action = models.CharField(max_length=32, choices=ACTIONS, default='alert')
    notify_emails = models.JSONField(default=list, blank=True)
    notify_sms = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    shadow_mode = models.BooleanField(default=True,
                                      help_text="Log incidents but do not execute action (recommended for first 2 weeks)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['company', 'severity', 'name']
        indexes = [models.Index(fields=['company', 'is_active', 'rule_type'])]

    def __str__(self):
        return f"{self.company.name} · {self.name} ({self.severity})"


class FraudIncident(models.Model):
    """A rule fired against one or more CallRecords."""

    STATUS = [
        ('open',           'Open'),
        ('acknowledged',   'Acknowledged'),
        ('resolved',       'Resolved'),
        ('false_positive', 'False positive'),
    ]

    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE,
                                related_name='fraud_incidents')
    rule = models.ForeignKey(FraudRule, on_delete=models.SET_NULL, null=True,
                             related_name='incidents')
    severity = models.CharField(max_length=10, choices=FraudRule.SEVERITY)
    summary = models.CharField(max_length=255)
    detail = models.JSONField(default=dict)
    triggering_call = models.ForeignKey(
        'cdr3cx.CallRecord', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    status = models.CharField(max_length=20, choices=STATUS, default='open', db_index=True)
    detected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resolved_fraud_incidents',
    )
    notification_dispatched = models.BooleanField(default=False)
    action_executed = models.CharField(max_length=32, blank=True, default='')

    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['company', 'status', '-detected_at']),
            models.Index(fields=['severity', 'status']),
        ]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.summary}"


# ---------------------------------------------------------------------------
# P4.1 / P4.2 — Invoicing & payments (multi-currency + tax)
# ---------------------------------------------------------------------------
class Invoice(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_ISSUED = 'issued'
    STATUS_PAID = 'paid'
    STATUS_VOID = 'void'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'), (STATUS_ISSUED, 'Issued'),
        (STATUS_PAID, 'Paid'), (STATUS_VOID, 'Void'),
    ]

    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='invoices')
    number = models.CharField(max_length=40, unique=True)
    period_start = models.DateField()
    period_end = models.DateField()
    currency = models.CharField(max_length=3, default='SAR')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    tax_rule = models.ForeignKey(
        'TaxRule', null=True, blank=True, on_delete=models.SET_NULL, related_name='invoices')
    issued_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('company', 'period_start', 'period_end')
        ordering = ['-period_start', 'company']
        indexes = [models.Index(fields=['company', 'status'])]

    def __str__(self):
        return f"{self.number} — {self.company.name} ({self.status})"

    @property
    def amount_paid(self):
        return sum((p.amount for p in self.payments.all()), Decimal('0'))

    @property
    def balance_due(self):
        return self.total - self.amount_paid

    def record_payment(self, amount, method='manual', reference=''):
        """Attach a payment; flip to paid once the balance is covered."""
        amount = Decimal(str(amount))
        pay = self.payments.create(
            amount=amount, currency=self.currency, method=method, reference=reference)
        if self.balance_due <= Decimal('0') and self.status != self.STATUS_VOID:
            self.status = self.STATUS_PAID
            self.paid_at = timezone.now()
            self.save(update_fields=['status', 'paid_at'])
        return pay


class InvoiceLineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    description = models.CharField(max_length=120)
    category = models.CharField(max_length=40, blank=True, default='')
    quantity = models.IntegerField(default=0, help_text='Number of calls')
    unit = models.CharField(max_length=20, default='calls')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ['-amount']

    def __str__(self):
        return f"{self.description}: {self.amount}"


class Payment(models.Model):
    METHOD_CHOICES = [
        ('manual', 'Manual'), ('card', 'Card'), ('bank', 'Bank transfer'),
        ('gateway', 'Payment gateway'),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='SAR')
    method = models.CharField(max_length=12, choices=METHOD_CHOICES, default='manual')
    reference = models.CharField(max_length=120, blank=True, default='')
    paid_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_at']

    def __str__(self):
        return f"{self.amount} {self.currency} for {self.invoice.number}"
