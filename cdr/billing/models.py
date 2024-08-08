from django.db import models
from django.utils import timezone
from accounts.models import Extension
from cdr3cx.models import CallRecord

from django.db import models
from django.utils import timezone
from accounts.models import Extension
from .models import CallRecord

from decimal import Decimal

class UserQuota(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    extension = models.ForeignKey(Extension, on_delete=models.CASCADE)
    quota_limit = models.IntegerField(default=0)  # in amount
    balance = models.IntegerField(default=0)  # remaining in amount
    balance_frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='monthly')
    start_date = models.DateField(null=True, blank=True, default=timezone.now)
    is_recurring = models.BooleanField(default=True)
    is_excluded = models.BooleanField(default=False)

    def calculate_usage(self):
        if not self.start_date:
            print(f"Start date not set for extension {self.extension.extension}")
            return 0

        end_date = self.get_end_date()
        print(f"Calculating usage for extension {self.extension.extension} from {self.start_date} to {end_date}")

        calls = CallRecord.objects.filter(
            caller=self.extension.extension,
            call_time__range=(self.start_date, end_date),
            from_type='Extension',
            to_type__in=['LineSet', 'Line']
        )

        print(f"Filtered calls: {calls.count()}")
        total_minutes = sum(max(1, (call.duration or 0) // 60) for call in calls)
        print(f"Total minutes calculated: {total_minutes}")

        return total_minutes

    def get_end_date(self):
        if not self.start_date:
            return timezone.now().date()

        if self.balance_frequency == 'daily':
            return self.start_date + timezone.timedelta(days=1)
        elif self.balance_frequency == 'weekly':
            return self.start_date + timezone.timedelta(weeks=1)
        elif self.balance_frequency == 'monthly':
            return (self.start_date.replace(day=1) + timezone.timedelta(days=32)).replace(day=1) - timezone.timedelta(days=1)
        elif self.balance_frequency == 'yearly':
            return self.start_date.replace(year=self.start_date.year + 1) - timezone.timedelta(days=1)

    def calculate_bill(self):
        if not self.start_date:
            print(f"Start date not set for extension {self.extension.extension}")
            return 0

        end_date = self.get_end_date()
        calls = CallRecord.objects.filter(
            caller=self.extension.extension,
            call_time__range=(self.start_date, end_date)
        )

        total_cost = Decimal(0)
        unmatched_calls = []
        for call in calls:
            rate = self.get_call_rate(call.callee)
            if rate:
                call_duration_minutes = Decimal((call.duration or 0) / 60)  # Convert seconds to minutes
                call_cost = call_duration_minutes * rate.rate_per_min
                total_cost += call_cost
            else:
                unmatched_calls.append(call.callee)

        if unmatched_calls:
            print(f"Unmatched calls for extension {self.extension.extension}: {unmatched_calls}")

        return total_cost

    def get_call_rate(self, callee):
        for rate in CallRate.objects.all():
            criteria_list = rate.matching_criteria.split(',')
            for criteria in criteria_list:
                if callee.startswith(criteria.strip()):
                    return rate
        return None

    def remaining_balance(self):
        usage = self.calculate_usage()
        return max(0, self.balance - usage)

    def __str__(self):
        return f"{self.extension.extension} - {self.balance_frequency} quota starting {self.start_date or 'N/A'}"

    class Meta:
        unique_together = ('extension', 'start_date', 'balance_frequency')
        ordering = ['-start_date', 'extension__extension']

# Ensure that when an Extension is created, a UserQuota instance is created with a default start_date
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Extension)
def create_user_quota(sender, instance, created, **kwargs):
    if created:
        UserQuota.objects.create(extension=instance)

# Ensure that when an Extension is created, a UserQuota instance is created with a default start_date
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Extension)
def create_user_quota(sender, instance, created, **kwargs):
    if created:
        UserQuota.objects.create(extension=instance)




class CallRate(models.Model):
    CALL_TYPE_CHOICES = [
        ('off_net', 'Off-Net Calls'),
        ('mobile', 'Mobile'),
        ('uan_9200', 'UAN (9200)'),
        ('uan_calling', 'UAN Calling Party'),
        ('uan_called', 'UAN Called Party'),
        ('toll_free_on_net', 'Toll Free (inbound- on Net)'),
        ('toll_free_off_net', 'Toll Free (inbound- off Net)'),
        ('inbound_toll_free_mobile', 'Inbound Toll-Free (Mobile)'),
        ('inbound_toll_free_uan_9200', 'Inbound Toll-Free (UAN-9200)'),
        ('international', 'International Calls'),
    ]

    call_type = models.CharField(max_length=50, choices=CALL_TYPE_CHOICES, unique=True)
    rate_per_min = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    matching_criteria = models.CharField(max_length=255, blank=True, help_text="Comma separated list of matching criteria numbers")

    def __str__(self):
        return f"{self.get_call_type_display()} - {self.rate_per_min} SAR/Min"