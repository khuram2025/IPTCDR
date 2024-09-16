# management/commands/reset_quotas.py

from django.core.management.base import BaseCommand
from cdr3cx.models import UserQuota

class Command(BaseCommand):
    help = 'Checks and resets user quotas if needed'

    def handle(self, *args, **options):
        user_quotas = UserQuota.objects.all()
        for user_quota in user_quotas:
            user_quota.check_and_reset_if_needed()
        self.stdout.write(self.style.SUCCESS('Successfully checked and reset quotas'))