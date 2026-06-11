"""Rebuild materialized daily call rollups (P3.5).

Full rebuild:  manage.py build_call_rollups --days-back 400
"""
from django.core.management.base import BaseCommand

from acd.rollups import build_call_rollups


class Command(BaseCommand):
    help = 'Rebuild CallDailyRollup rows from CallRecord (idempotent)'

    def add_arguments(self, parser):
        parser.add_argument('--days-back', type=int, default=400)
        parser.add_argument('--company-id', type=int)

    def handle(self, *args, **o):
        n = build_call_rollups(company_id=o['company_id'], days_back=o['days_back'])
        self.stdout.write(self.style.SUCCESS(f'Upserted {n} company-day rollup rows'))
