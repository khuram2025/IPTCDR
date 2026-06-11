from decimal import Decimal
from django.db import models,transaction
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models

from notifications.models import Notification
from .utils import get_country_from_number
import phonenumbers
from django.template.loader import render_to_string
from phonenumbers import geocoder, NumberParseException
import re
from django.core.mail import send_mail
from django.conf import settings
from .notification_utils import resolve_extension_alert_email

from accounts.models import Company, Extension


def _enqueue_quota_enforcement(extension_id):
    """Best-effort enqueue of the PBX block/unblock task (P4.3). Falls back to a
    synchronous call if the broker is unavailable; never propagates errors into the
    ingest transaction."""
    try:
        from cdr3cx.tasks import enforce_quota_state
        try:
            enforce_quota_state.delay(extension_id)
        except Exception:
            enforce_quota_state(extension_id)
    except Exception as e:
        logger.warning("quota enforcement enqueue failed for ext %s: %s", extension_id, e)


class CallPattern(models.Model):
    CALL_TYPE_CHOICES = [
        ('mobile', 'Mobile'),
        ('national', 'National'),
        ('international', 'International'),
        ('local', 'Local'),
        ('unknown', 'Unknown'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='call_patterns')
    name = models.CharField(max_length=100, default="", help_text="Name of the calling rule")
    pattern = models.CharField(max_length=20, help_text="Pattern for matching callee numbers, e.g., +1, 059")
    call_type = models.CharField(max_length=20, choices=CALL_TYPE_CHOICES)
    rate_per_min = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Rate per minute in SAR")

    description = models.CharField(max_length=100, null=True, blank=True, help_text="Optional description of the pattern")

    def __str__(self):
        return f"{self.company.name} - {self.name} ({self.pattern})"

    def get_regex_pattern(self):
        if self.pattern == '+':
            return r'^\+\d+'
        elif self.pattern == '00':
            return r'^00\d+'
        elif self.pattern == '^\d{4}$':
            return self.pattern
        else:
            return f'^{re.escape(self.pattern)}.*$'

    def matches(self, number):
        try:
            pattern = self.get_regex_pattern()
            return re.match(pattern, number) is not None
        except re.error:
            return False

@receiver(post_save, sender=CallPattern)
def apply_pattern_to_call_records(sender, instance, **kwargs):
    from cdr3cx.tasks import reapply_call_pattern
    reapply_call_pattern.delay(instance.pk)

import logging
logger = logging.getLogger(__name__)

class CallRecord(models.Model):
    SOURCE_PBX_CHOICES = [
        ('3cx', '3CX'),
        ('cisco_cucm', 'Cisco CUCM'),
        ('ms_teams', 'Microsoft Teams'),
        ('webex_calling', 'Webex Calling'),
        ('zoom_phone', 'Zoom Phone'),
        ('asterisk', 'Asterisk / FreePBX'),
        ('yeastar', 'Yeastar'),
        ('grandstream', 'Grandstream'),
        ('generic_sip', 'Generic SIP'),
        ('avaya', 'Avaya'),
        ('mitel', 'Mitel'),
    ]

    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='call_records')
    source_pbx = models.CharField(max_length=20, choices=SOURCE_PBX_CHOICES, default='3cx', db_index=True,
                                  help_text="Originating PBX platform — set by ingestion adapter")
    external_id = models.CharField(max_length=128, null=True, blank=True, db_index=True,
                                   help_text="PBX-side unique ID (CUCM pkid, Teams callRecord.id, Zoom call_id, etc.)")
    correlation_id = models.CharField(max_length=128, null=True, blank=True, db_index=True,
                                      help_text="Multi-leg correlation (Webex Correlation ID, Zoom call_uuid)")
    raw_data = models.JSONField(null=True, blank=True,
                                help_text="Original vendor payload preserved for re-processing")

    # Quality of Service (where adapter provides)
    mos = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True,
                              help_text="Mean Opinion Score 1.0-5.0")
    jitter_ms = models.IntegerField(null=True, blank=True)
    packet_loss_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    codec = models.CharField(max_length=32, null=True, blank=True)

    caller = models.CharField(max_length=20, null=True, blank=True)
    callee = models.CharField(max_length=20)
    call_time = models.DateTimeField(null=True)
    external_number = models.CharField(max_length=20, default='Unknown')
    country = models.CharField(max_length=50, default='Unknown', blank=True)
    duration = models.IntegerField(null=True, blank=True)  # Duration in seconds
    time_answered = models.DateTimeField(null=True, blank=True)
    time_end = models.DateTimeField(null=True, blank=True)
    reason_terminated = models.CharField(max_length=50, null=True, blank=True)
    reason_changed = models.CharField(max_length=50, null=True, blank=True)
    missed_queue_calls = models.CharField(max_length=50, null=True, blank=True)

    from_no = models.CharField(max_length=20, null=True, blank=True)
    to_no = models.CharField(max_length=20, null=True, blank=True)
    to_dn = models.CharField(max_length=20, null=True, blank=True)
    final_number = models.CharField(max_length=20, null=True, blank=True)
    final_dn = models.CharField(max_length=20, null=True, blank=True)
    from_type = models.CharField(max_length=20, null=True, blank=True)
    to_type = models.CharField(max_length=20, null=True, blank=True)
    final_type = models.CharField(max_length=20, null=True, blank=True)
    from_dispname = models.CharField(max_length=50, null=True, blank=True)
    to_dispname = models.CharField(max_length=50, null=True, blank=True)
    final_dispname = models.CharField(max_length=50, null=True, blank=True)


    # ACD / canonical analytics columns (P1 — nullable, backfilled async)
    DIRECTION_CHOICES = [
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
        ('internal', 'Internal'),
        ('unknown', 'Unknown'),
    ]
    INGEST_TRANSPORT_CHOICES = [
        ('socket', 'Legacy Socket'),
        ('db_pull', '3CX DB Pull'),
        ('csv', 'CSV Import'),
        ('api', 'REST API'),
    ]

    direction = models.CharField(
        max_length=16, choices=DIRECTION_CHOICES, null=True, blank=True, db_index=True,
    )
    ring_time = models.IntegerField(null=True, blank=True, help_text='Ring time in seconds')
    wait_time = models.IntegerField(null=True, blank=True, help_text='Queue wait in seconds')
    hold_time = models.IntegerField(null=True, blank=True, help_text='Hold time in seconds')
    wrap_time = models.IntegerField(null=True, blank=True, help_text='After-call work in seconds')
    abandoned = models.BooleanField(null=True, blank=True, db_index=True)
    call_disposition = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    queue = models.ForeignKey(
        'acd.Queue', null=True, blank=True, on_delete=models.SET_NULL, related_name='call_records',
    )
    agent = models.ForeignKey(
        'acd.Agent', null=True, blank=True, on_delete=models.SET_NULL, related_name='call_records',
    )
    currency = models.CharField(max_length=3, default='SAR', blank=True)
    ingest_transport = models.CharField(
        max_length=16, choices=INGEST_TRANSPORT_CHOICES, default='socket', blank=True,
    )

    call_category = models.CharField(max_length=20, null=True, blank=True, choices=CallPattern.CALL_TYPE_CHOICES)
    call_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Rate per minute in SAR")
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Total cost of the call")

    def __str__(self):
        return f"{self.caller} -> {self.callee} at {self.call_time}"
    
    def categorize_call(self):
        logger.info(f"Categorizing call for number: {self.callee}")
        patterns = self.company.call_patterns.all().order_by('-pattern')
        logger.info(f"Number of patterns found for company {self.company.name}: {patterns.count()}")

        for pattern in patterns:
            logger.info(f"Checking pattern: {pattern.pattern}")
            if pattern.matches(self.callee):
                logger.info(f"Match found: {self.callee} matches {pattern.pattern}")
                self.call_category = pattern.call_type
                self.call_rate = Decimal(str(pattern.rate_per_min))
                logger.info(f"Set call category to {self.call_category} and rate to {self.call_rate}")
                return

        # If no pattern matched, categorize as 'unknown'
        logger.warning(f"No pattern matched for callee: {self.callee}. Setting call category to 'Unknown'.")
        unknown_pattern = self.company.call_patterns.filter(call_type='unknown').first()
        if unknown_pattern:
            self.call_category = 'unknown'
            self.call_rate = Decimal(str(unknown_pattern.rate_per_min))
        else:
            self.call_category = 'unknown'
            self.call_rate = Decimal('0.00')
        logger.info(f"Set call category to {self.call_category} and rate to {self.call_rate}")


    def calculate_total_cost(self):
        logger.info(f"Calculating total cost for call: duration={self.duration} seconds")
        if self.duration:
            # Ensure duration_minutes is a Decimal
            duration_minutes = Decimal((self.duration + 59) // 60)  # Round up to the nearest whole minute
            logger.info(f"Duration in minutes: {duration_minutes}")

            # Convert self.call_rate to Decimal if it's not already
            call_rate = Decimal(self.call_rate) if not isinstance(self.call_rate, Decimal) else self.call_rate
            logger.info(f"Current call rate: {call_rate}")

            # Calculate the total cost using Decimal for both operands
            self.total_cost = duration_minutes * call_rate
            logger.info(f"Calculated total cost: {self.total_cost}")
        else:
            logger.warning("Duration is None or 0, setting total cost to 0")
            self.total_cost = Decimal('0.00')
        return self.total_cost

   
    def save(self, *args, **kwargs):
        # P0.7: per-record print() storm removed; verbose tracing demoted to
        # logger.debug so production (root logger at INFO) stays quiet while the
        # detail remains available by raising the log level.
        logger.debug("CallRecord.save start: caller=%s callee=%s duration=%s",
                     self.caller, self.callee, self.duration)
        is_new_record = not self.pk
        try:
            with transaction.atomic():
                if is_new_record:
                    old_total_cost = Decimal('0.00')
                else:
                    old_record = CallRecord.objects.get(pk=self.pk)
                    old_total_cost = old_record.total_cost

                # Determine the country for international calls
                self.country = get_country_from_number(self.callee)
                # Categorize and cost the call
                self.categorize_call()
                self.calculate_total_cost()
                logger.debug("CallRecord.save costing: old=%s new=%s",
                             old_total_cost, self.total_cost)

                super().save(*args, **kwargs)

                # Update quota (row-locked inside this same transaction)
                self.update_user_quota(old_total_cost)
        except Exception as e:
            logger.error("Error during CallRecord.save: %s", e)
            raise  # Re-raise after logging
        logger.debug("CallRecord.save done id=%s", self.pk)

    def update_user_quota(self, old_total_cost):
        logger.info(f"Starting update_user_quota with old_total_cost={old_total_cost}")
        try:
            extension = Extension.objects.get(extension=self.caller, company=self.company)
            logger.debug("Found extension: %s", extension)
            # P0.7: lock the quota row for the duration of this transaction so
            # concurrent CDR inserts for the same extension cannot race on the
            # balance (save() already wraps this call in transaction.atomic()).
            user_quota = UserQuota.objects.select_for_update().get(extension=extension)
            logger.debug("UserQuota before: total=%s used=%s",
                         user_quota.total_amount, user_quota.used_amount)
            
            user_quota.check_and_reset_if_needed()
            logger.info(f"After check_and_reset_if_needed: total_amount = {user_quota.total_amount}, used_amount = {user_quota.used_amount}")
            
            amount_to_deduct = self.total_cost - Decimal(str(old_total_cost))
            logger.info(f"Amount to deduct: {amount_to_deduct}")
            
            if amount_to_deduct > Decimal('0'):
                user_quota.deduct_balance(amount_to_deduct)
                logger.info(f"Deducted {amount_to_deduct} from quota. New used amount: {user_quota.used_amount}, Remaining balance: {user_quota.remaining_balance}")
            elif amount_to_deduct < Decimal('0'):
                user_quota.add_balance(abs(amount_to_deduct))
                logger.info(f"Added {abs(amount_to_deduct)} to quota due to cost reduction. New balance: {user_quota.total_amount - user_quota.used_amount}")
            else:
                logger.info("No change in total cost, quota remains the same.")

            # P4.3 — if the exhausted/replenished state changed, enforce it on the
            # PBX asynchronously *after commit* so the hot ingest path never makes a
            # network call. Idempotent: the task no-ops when state already matches.
            if user_quota.should_block() != user_quota.is_blocked:
                ext_id = user_quota.extension_id
                transaction.on_commit(
                    lambda: _enqueue_quota_enforcement(ext_id))
        except Extension.DoesNotExist:
            logger.warning(f"Warning: No extension found for {self.caller}")
        except UserQuota.DoesNotExist:
            logger.warning(f"Warning: No quota set for extension {self.caller}")
        except Exception as e:
            logger.error(f"Unexpected error in quota deduction: {str(e)}")
            raise
        
    class Meta:
        ordering = ['-call_time']  # Example of ordering by call_time descending



class Quota(models.Model):
    FREQUENCY_CHOICES = [
        ('monthly', 'Monthly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ]
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='quotas')
    frequency = models.CharField(
        max_length=10, 
        choices=FREQUENCY_CHOICES, 
        default='monthly',
        null=True,  # Allow NULL values
        blank=True  # Allow blank values in forms
    )

    def __str__(self):
        frequency_display = self.get_frequency_display() if self.frequency else 'No frequency set'
        return f"{self.name} - {self.amount} SAR ({frequency_display})"
from dateutil.relativedelta import relativedelta

class UserQuota(models.Model):
    extension = models.OneToOneField('accounts.Extension', on_delete=models.CASCADE, related_name='quota')
    quota = models.ForeignKey('Quota', on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    used_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_reset = models.DateTimeField(default=timezone.now)
    # P4.3 — enforcement state: True once external calls have been blocked on the
    # PBX for this extension because its balance was exhausted. Lets the enforcement
    # task act only on transitions (idempotent) and the UI show who is blocked.
    is_blocked = models.BooleanField(default=False)

    def __str__(self):
        return f"Quota for {self.extension}"

    @property
    def remaining_balance(self):
        return self.total_amount - self.used_amount

    def should_block(self):
        """True when this extension's external calling should be blocked: it has a
        quota assigned and the balance is exhausted (used >= total)."""
        return bool(self.quota) and self.remaining_balance <= Decimal('0')

    def reset_quota(self):
        if self.quota:
            logger.info(f"Resetting quota for {self.extension}. Old total: {self.total_amount}")
            self.total_amount = self.quota.amount
            self.used_amount = Decimal('0')
            self.last_reset = timezone.now()
            self.save()
            logger.info(f"Quota reset. New total: {self.total_amount}")
    
    def add_custom_balance(self, amount):
        amount = Decimal(str(amount))
        if amount > 0:
            logger.info(f"Adding custom balance of {amount} to {self.extension}")
            self.total_amount += amount
            self.save()
            logger.info(f"New total amount: {self.total_amount}")
            return True
        logger.warning(f"Invalid amount for custom balance addition: {amount}")
        return False

    def deduct_balance(self, amount):
        amount = Decimal(str(amount))
        logger.info(f"Attempting to deduct {amount} from balance {self.remaining_balance}")
        
        # Remove the check for remaining balance
        self.used_amount += amount
        self.save()
        logger.info(f"Successfully deducted {amount}. New used amount: {self.used_amount}, Remaining balance: {self.remaining_balance}")
        
        # Optionally, you can still return False if the balance goes negative
        return self.remaining_balance >= 0

    def should_send_quota_alert(self):
        if self.quota and self.quota.amount > 0:
            used_percentage = (self.used_amount / self.total_amount) * 100
            logger.info(f"Quota used: {used_percentage}%")
            return used_percentage >= 90
        return False

    def send_quota_alert(self):
        logger.info(f"Sending quota alert for {self.extension}")

        # Prepare email content
        subject = f"Quota Alert for Extension {self.extension.extension}"
        message = render_to_string('notifications/quota_alert_email.html', {
            'extension': self.extension.extension,
            'remaining_balance': self.remaining_balance,
            'quota_amount': self.quota.amount,
        })
        recipient = resolve_extension_alert_email(self.extension)

        # Send the email
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )

        # Create a Notification record
        Notification.objects.create(
            recipient=recipient,
            subject=subject,
            message=message,
        )

    def add_balance(self, amount):
        amount = Decimal(str(amount))
        # logger.info(f"Adding {amount} to total amount {self.total_amount}")
        self.total_amount += amount
        self.save()
        # logger.info(f"New total amount: {self.total_amount}")

    def should_reset(self):
        if not self.quota:
           
            return False

        if not self.quota.frequency:
           
            return False

        now = timezone.now()
        if self.quota.frequency == 'monthly':
            next_reset = self.last_reset + relativedelta(months=1)
        elif self.quota.frequency == 'daily':
            next_reset = self.last_reset + relativedelta(days=1)
        elif self.quota.frequency == 'weekly':
            next_reset = self.last_reset + relativedelta(weeks=1)
        else:
            # logger.warning(f"Unknown frequency '{self.quota.frequency}' for {self.extension}")
            return False

        should_reset = now >= next_reset
        logger.info(f"Quota for {self.extension}: Last reset: {self.last_reset}, Next reset: {next_reset}, Current time: {now}, Should reset: {should_reset}")
        return should_reset

    def check_and_reset_if_needed(self):
        # logger.info(f"Checking if quota needs reset for {self.extension}")
        if self.should_reset():
            logger.info(f"Resetting quota for {self.extension}")
            self.reset_quota()
        else:
            logger.info(f"Quota reset not needed for {self.extension}")


@receiver(post_save, sender=Extension)
def create_user_quota(sender, instance, created, **kwargs):
    if created:
        default_quota = Quota.objects.filter(company=instance.company).first()
        UserQuota.objects.create(extension=instance, quota=default_quota)

@receiver(post_save, sender=UserQuota)
def set_initial_balance(sender, instance, created, **kwargs):
    if created and instance.quota:
        instance.total_amount = instance.quota.amount
        instance.used_amount = Decimal('0')
        instance.save()


