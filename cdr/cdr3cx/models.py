from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
from .utils import get_country_from_number
import phonenumbers

from phonenumbers import geocoder, NumberParseException
import re

from accounts.models import Company

class CallPattern(models.Model):
    CALL_TYPE_CHOICES = [
        ('mobile', 'Mobile'),
        ('national', 'National'),
        ('international', 'International'),
        ('local', 'Local'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='call_patterns')
    pattern = models.CharField(max_length=20, help_text="Pattern for matching callee numbers, e.g., +1, 059")
    call_type = models.CharField(max_length=20, choices=CALL_TYPE_CHOICES)
    rate_per_min = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Rate per minute in SAR")

    description = models.CharField(max_length=100, null=True, blank=True, help_text="Optional description of the pattern")

    def __str__(self):
        return f"{self.company.name} - {self.call_type} ({self.pattern})"

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
        patterns = self.company.call_patterns.all()

        # print(f"Attempting to categorize call for callee: {self.callee}")

        if not patterns:
            # print(f"No call patterns found for company: {self.company.name}")
            self.call_category = 'Unknown'
            return

        for pattern in patterns:
            # Convert the pattern to a regex pattern
            regex_pattern = pattern.pattern.replace('x', r'\d').replace('X', r'\d').replace('+', r'\+?')
            regex_pattern = '^' + regex_pattern + r'.*$'
            # print(f"Checking pattern: {pattern.pattern} -> Regex: {regex_pattern}")

            # Use regex to check if the callee matches the pattern
            if re.match(regex_pattern, self.callee):
                # print(f"Match found: {self.callee} matches {pattern.pattern}")
                self.call_category = pattern.call_type
                self.call_rate = pattern.rate_per_min
                return  # Exit once a match is found

        # print(f"No pattern matched for callee: {self.callee}. Setting call category to 'Unknown'.")
        self.call_category = 'Unknown'

    def calculate_total_cost(self):
        """
        Calculate total cost based on the duration and rate per minute.
        """
        if self.duration:
            duration_minutes = (self.duration + 59) // 60  # Round up to the nearest whole minute
            self.total_cost = duration_minutes * self.call_rate

    def save(self, *args, **kwargs):
            try:
                if not self.company:
                    self.company = Company.objects.get_or_create(name="Channab")[0]

                if not self.pk or 'update_fields' not in kwargs or 'country' in kwargs.get('update_fields', []):
                    country_info = get_country_from_number(self.callee)
                    self.country = country_info
                    if 'Internal Company Call' in country_info:
                        self.call_type = 'Internal'
                    elif 'Saudi Arabia' in country_info:
                        self.call_type = 'National'
                    elif 'International' in country_info:
                        self.call_type = 'International'
                    else:
                        self.call_type = 'Unknown'

                if not self.pk:  # This is a new record
                    print(f"Saving new CallRecord: {self.caller} -> {self.callee} ({self.call_type}) at {self.call_time}")
                    self.categorize_call()
                    self.calculate_total_cost()
                else:  # This is an existing record
                    if 'update_fields' in kwargs:
                        print(f"Updating fields {kwargs['update_fields']} for CallRecord: {self.caller} -> {self.callee}")
                    else:
                        print(f"Updating CallRecord: {self.caller} -> {self.callee}")

            except Exception as e:
                print(f"Error during save: {str(e)}")
            
            super().save(*args, **kwargs)

    class Meta:
        ordering = ['-call_time']  # Example of ordering by call_time descending

    
class RoutingRule(models.Model):
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True, related_name='routing_rules')
    external_number = models.CharField(max_length=20)
    original_caller = models.CharField(max_length=20)
    route_to = models.CharField(max_length=20)

    def __str__(self):
        return f"Route {self.external_number} to {self.route_to} for {self.original_caller}"
    
    def save(self, *args, **kwargs):
        if not self.company:
            self.company = Company.objects.get_or_create(name="Channab")[0]
        super().save(*args, **kwargs)
