from django.db import models
from django.utils import timezone
from datetime import timedelta

from django.db import models

from accounts.models import Company


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

    def __str__(self):
        return f"{self.caller} -> {self.callee} at {self.call_time}"
    
    def save(self, *args, **kwargs):
        if not self.company:
            self.company = Company.objects.get_or_create(name="Channab")[0]
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
