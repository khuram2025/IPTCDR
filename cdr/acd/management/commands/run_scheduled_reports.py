"""Process due scheduled reports (P3.1). Mirrors the celery-beat task; handy for
cron fallback or manual runs:  manage.py run_scheduled_reports
"""
from django.core.management.base import BaseCommand

from acd.tasks import run_due_scheduled_reports


class Command(BaseCommand):
    help = 'Generate + deliver all scheduled reports whose next_run_at is due'

    def handle(self, *args, **o):
        res = run_due_scheduled_reports()
        self.stdout.write(self.style.SUCCESS(f"Ran {res['ran']} due report(s)"))
