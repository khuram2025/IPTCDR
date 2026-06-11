"""Sync real user extensions from the 3CX XAPI into accounts.Extension.

Initial backfill / manual run:
  manage.py sync_3cx_users                 # all companies with PBX creds
  manage.py sync_3cx_users --company Smasco
Ongoing is handled by the celery-beat task (every 6h).
"""
from django.core.management.base import BaseCommand

from acd.tasks import sync_3cx_users


class Command(BaseCommand):
    help = 'Sync user extensions from the 3CX XAPI into accounts.Extension (one-way).'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int)
        parser.add_argument('--company', type=str,
                            help='Company name (resolved to its id)')
        parser.add_argument('--no-verify-tls', action='store_true',
                            help='Disable TLS verification (self-signed 3CX certs)')

    def handle(self, *args, **o):
        company_id = o.get('company_id')
        if o.get('company') and not company_id:
            from accounts.models import Company
            c = Company.objects.filter(name=o['company']).first()
            if not c:
                self.stderr.write(self.style.ERROR(f"No company named {o['company']!r}"))
                return
            company_id = c.id

        summary = sync_3cx_users(
            company_id=company_id,
            verify_tls=not o['no_verify_tls'],
        )
        if not summary:
            self.stdout.write(self.style.WARNING(
                'No companies synced (none have pbx_api_url/user/password set).'))
            return
        for name, s in summary.items():
            if 'error' in s:
                self.stdout.write(self.style.ERROR(f"{name}: ERROR {s['error']}"))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"{name}: pulled {s['pulled']}, created {s['created']}, "
                    f"updated {s['updated']}, failed {s['failed']}, "
                    f"deactivated {s['deactivated']}"))
