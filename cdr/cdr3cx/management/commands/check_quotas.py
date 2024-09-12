from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from decimal import Decimal

from cdr3cx.models import UserQuota


class Command(BaseCommand):
    help = 'Checks user quotas and sends email alerts for low balances'

    def handle(self, *args, **kwargs):
        self.stdout.write('Checking user quotas...')
        
        user_quotas = UserQuota.objects.all()

        for user_quota in user_quotas:
            if user_quota.quota:
                total_quota = user_quota.quota.amount
                remaining_balance = user_quota.remaining_balance
                remaining_percentage = (remaining_balance / total_quota) * 100

                if remaining_percentage <= 50:
                    subject = f"Low Balance Alert for Extension {user_quota.extension}"
                    message = f"""
                    Dear Administrator,

                    The remaining balance for extension {user_quota.extension} is now at {remaining_percentage:.2f}% of its total quota.

                    Total Quota: {total_quota}
                    Remaining Balance: {remaining_balance}

                    Please take necessary actions.

                    Best regards,
                    Your System
                    """
                    from_email = settings.DEFAULT_FROM_EMAIL
                    recipient_list = ['khuram2025@gmail.com']

                    try:
                        send_mail(
                            subject,
                            message,
                            from_email,
                            recipient_list,
                            fail_silently=False,
                        )
                        self.stdout.write(self.style.SUCCESS(f'Email sent for extension {user_quota.extension}'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Failed to send email for extension {user_quota.extension}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS('Quota check completed'))