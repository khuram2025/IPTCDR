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

from accounts.models import Company, Extension

class CallPattern(models.Model):
    CALL_TYPE_CHOICES = [
        ('mobile', 'Mobile'),
        ('national', 'National'),
        ('international', 'International'),
        ('local', 'Local'),
        ('unknown', 'Unknown'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='call_patterns')
    pattern = models.CharField(max_length=20, help_text="Pattern for matching callee numbers, e.g., +1, 059")
    call_type = models.CharField(max_length=20, choices=CALL_TYPE_CHOICES)
    rate_per_min = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Rate per minute in SAR")

    description = models.CharField(max_length=100, null=True, blank=True, help_text="Optional description of the pattern")

    def __str__(self):
        return f"{self.company.name} - {self.call_type} ({self.pattern})"

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
    # Fetch all call records that match the pattern and have to_type as 'Line'
    matching_records = CallRecord.objects.filter(
        company=instance.company,
        callee__startswith=instance.pattern.replace('x', ''),
        to_type='Line'
    )

    # Calculate the cost for each matching record
    for record in matching_records:
        # Convert duration to minutes, rounding up to the next whole minute if there are extra seconds
        duration_minutes = (record.duration + 59) // 60  # Adding 59 ensures rounding up to the next whole minute

        # Assign the call category and rate per minute
        record.call_category = instance.call_type
        record.call_rate = instance.rate_per_min

        # Calculate the total cost
        record.total_cost = duration_minutes * instance.rate_per_min

        # Save the record with the updated values
        record.save()

import logging
logger = logging.getLogger(__name__)

class CallRecord(models.Model):
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='call_records')
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
            logger.info("--- Starting save process for CallRecord ---")
            print("--- Starting save process for CallRecord ---")  # Console output
            logger.info(f"Initial state: caller={self.caller}, callee={self.callee}, duration={self.duration}, total_cost={self.total_cost}")
            print(f"Initial state: caller={self.caller}, callee={self.callee}, duration={self.duration}, total_cost={self.total_cost}")  # Console output
            
            is_new_record = not self.pk
            
            try:
                with transaction.atomic():
                    if is_new_record:
                        old_total_cost = Decimal('0.00')
                        logger.info("This is a new CallRecord")
                        print("This is a new CallRecord")  # Console output
                    else:
                        old_record = CallRecord.objects.get(pk=self.pk)
                        old_total_cost = old_record.total_cost
                        logger.info(f"This is an existing CallRecord. Old total cost: {old_total_cost}")
                        print(f"This is an existing CallRecord. Old total cost: {old_total_cost}")  # Console output

                    # Determine and save the country for international calls
                    logger.info(f"Before determining country, Caller: {self.caller}, Callee: {self.callee}")
                    print(f"Before determining country, Caller: {self.caller}, Callee: {self.callee}")
                    self.country = get_country_from_number(self.callee)
                    logger.info(f"Determined country for callee number: {self.country}")
                    print(f"Determined country for callee number: {self.country}")  # Console output

                    # Categorize the call
                    logger.info("Categorizing call...")
                    print("Categorizing call...")  # Console output
                    self.categorize_call()

                    logger.info("Calculating total cost...")
                    print("Calculating total cost...")  # Console output
                    self.calculate_total_cost()
                    logger.info(f"After cost calculation: old_total_cost={old_total_cost}, new_total_cost={self.total_cost}")
                    print(f"After cost calculation: old_total_cost={old_total_cost}, new_total_cost={self.total_cost}")  # Console output

                    # Save the record
                    logger.info("Calling super().save()")
                    print("Calling super().save()")  # Console output
                    super().save(*args, **kwargs)

                    # Update quota
                    logger.info("Updating user quota...")
                    print("Updating user quota...")  # Console output
                    self.update_user_quota(old_total_cost)

            except Exception as e:
                logger.error(f"Error during save: {str(e)}")
                print(f"Error during save: {str(e)}")  # Console output
                raise  # Re-raise the exception after logging
            
            logger.info("--- Finished save process for CallRecord ---")
            print("--- Finished save process for CallRecord ---")  # Console output

    def update_user_quota(self, old_total_cost):
        logger.info(f"Starting update_user_quota with old_total_cost={old_total_cost}")
        try:
            extension = Extension.objects.get(extension=self.caller, company=self.company)
            logger.info(f"Found extension: {extension}")
            user_quota = UserQuota.objects.get(extension=extension)
            logger.info(f"Found UserQuota: current total_amount = {user_quota.total_amount}, used_amount = {user_quota.used_amount}")
            
            user_quota.check_and_reset_if_needed()
            logger.info(f"After check_and_reset_if_needed: total_amount = {user_quota.total_amount}, used_amount = {user_quota.used_amount}")
            
            amount_to_deduct = self.total_cost - Decimal(str(old_total_cost))
            logger.info(f"Amount to deduct: {amount_to_deduct}")
            
            if amount_to_deduct > Decimal('0'):
                if not user_quota.deduct_balance(amount_to_deduct):
                    logger.warning(f"Warning: Quota exceeded for extension {self.caller}")
                else:
                    logger.info(f"Successfully deducted {amount_to_deduct} from quota. New balance: {user_quota.total_amount - user_quota.used_amount}")
            elif amount_to_deduct < Decimal('0'):
                user_quota.add_balance(abs(amount_to_deduct))
                logger.info(f"Added {abs(amount_to_deduct)} to quota due to cost reduction. New balance: {user_quota.total_amount - user_quota.used_amount}")
            else:
                logger.info("No change in total cost, quota remains the same.")
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
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='quotas')

    def __str__(self):
        return f"{self.name} - {self.amount} SAR"

class UserQuota(models.Model):
    extension = models.OneToOneField('accounts.Extension', on_delete=models.CASCADE, related_name='quota')
    quota = models.ForeignKey('Quota', on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    used_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_reset = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Quota for {self.extension}"

    @property
    def remaining_balance(self):
        return self.total_amount - self.used_amount

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
        if self.remaining_balance >= amount:
            self.used_amount += amount
            self.save()
            logger.info(f"Successfully deducted {amount}. New remaining balance: {self.remaining_balance}")
            return True
        logger.warning(f"Insufficient balance. Current: {self.remaining_balance}, Attempted deduction: {amount}")
        return False

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
        # recipient = self.extension.user.email 
        recipient = 'khuram2025@gmail.com'  # Assuming each extension has an associated user with an email

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
        logger.info(f"Adding {amount} to total amount {self.total_amount}")
        self.total_amount += amount
        self.save()
        logger.info(f"New total amount: {self.total_amount}")

    def should_reset(self):
        now = timezone.now()
        should_reset = (now.year > self.last_reset.year or 
                        (now.year == self.last_reset.year and now.month > self.last_reset.month))
        logger.info(f"Checking if quota should reset. Result: {should_reset}")
        print(f"Checking if quota should reset. Result: {should_reset}")  # Console output
        return should_reset

    def check_and_reset_if_needed(self):
        logger.info(f"Checking if quota needs reset for {self.extension}")
        print(f"Checking if quota needs reset for {self.extension}")  # Console output
        if self.should_reset():
            logger.info("Quota reset needed. Resetting...")
            print("Quota reset needed. Resetting...")  # Console output
            self.reset_quota()
            self.save()
        else:
            logger.info("Quota reset not needed")
            print("Quota reset not needed")  # Console output


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


