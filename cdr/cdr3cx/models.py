from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import models
import phonenumbers
from phonenumbers import geocoder, NumberParseException

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
    
    def save(self, *args, **kwargs):
        if not self.company:
            self.company = Company.objects.get_or_create(name="Channab")[0]
        super().save(*args, **kwargs)

    def categorize_call(self):
        # First, use patterns defined by the company
        patterns = self.company.call_patterns.all()
        for pattern in patterns:
            if self.callee.startswith(pattern.pattern):
                return pattern.call_type

        # If no pattern matches, try to detect if it's international
        try:
            parsed_number = phonenumbers.parse(self.callee, None)
            if phonenumbers.is_valid_number(parsed_number):
                if parsed_number.country_code != phonenumbers.region_code_for_number(parsed_number):
                    self.country = geocoder.country_name_for_number(parsed_number, "en")
                    return 'international'
        except NumberParseException:
            pass
        
        return 'Unknown'
    
    

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
