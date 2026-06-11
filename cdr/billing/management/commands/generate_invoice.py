"""Generate a tenant invoice for a billing period (P4.1/P4.2).

  manage.py generate_invoice --company-id 2 --month 2026-05 [--issue]
  manage.py generate_invoice --company-id 2 --start 2026-05-01 --end 2026-05-31
"""
import calendar
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from accounts.models import Company
from billing.services.invoicing import generate_invoice, reconcile


class Command(BaseCommand):
    help = 'Generate (or refresh) an invoice for a company and period'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)
        parser.add_argument('--month', help='YYYY-MM (whole calendar month)')
        parser.add_argument('--start', help='YYYY-MM-DD')
        parser.add_argument('--end', help='YYYY-MM-DD')
        parser.add_argument('--issue', action='store_true', help='Mark issued (set due date)')

    def handle(self, *args, **o):
        try:
            company = Company.objects.get(pk=o['company_id'])
        except Company.DoesNotExist:
            raise CommandError(f"No company id={o['company_id']}")

        if o['month']:
            y, m = (int(x) for x in o['month'].split('-'))
            start = date(y, m, 1)
            end = date(y, m, calendar.monthrange(y, m)[1])
        elif o['start'] and o['end']:
            start = datetime.strptime(o['start'], '%Y-%m-%d').date()
            end = datetime.strptime(o['end'], '%Y-%m-%d').date()
        else:
            raise CommandError('Provide --month or both --start and --end')

        inv = generate_invoice(company, start, end, issue=o['issue'])
        self.stdout.write(self.style.SUCCESS(
            f"{inv.number}: subtotal={inv.subtotal} tax={inv.tax_amount} "
            f"total={inv.total} {inv.currency} [{inv.status}] "
            f"reconciles={reconcile(inv)}"))
