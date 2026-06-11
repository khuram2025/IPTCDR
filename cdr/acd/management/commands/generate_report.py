"""Ad-hoc report generation to a file (P3.1).

  manage.py generate_report --company-id 2 --type queue_performance \
      --window last_30_days --format xlsx [--email a@x.com,b@y.com]
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Company
from acd.reports import REPORT_TYPES, WINDOWS
from acd.tasks import generate_report_file, _email_report_run


class Command(BaseCommand):
    help = 'Generate a single report to a file (and optionally email it)'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)
        parser.add_argument('--type', required=True, choices=list(REPORT_TYPES))
        parser.add_argument('--window', default='yesterday', choices=list(WINDOWS))
        parser.add_argument('--format', default='xlsx',
                            choices=['csv', 'xlsx', 'pdf', 'html'])
        parser.add_argument('--email', help='Comma-separated recipients')

    def handle(self, *args, **o):
        try:
            company = Company.objects.get(pk=o['company_id'])
        except Company.DoesNotExist:
            raise CommandError(f"No company id={o['company_id']}")
        run = generate_report_file(company, o['type'], o['window'], o['format'])
        if run.status != 'success':
            raise CommandError(f"Generation failed: {run.error}")
        self.stdout.write(self.style.SUCCESS(
            f"{run.row_count} rows -> {run.file_path}"))
        if o['email']:
            recips = [e.strip() for e in o['email'].split(',') if e.strip()]
            ok = _email_report_run(run, recips)
            self.stdout.write(('Emailed to ' if ok else 'Email FAILED for ') + ', '.join(recips))
