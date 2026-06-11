"""Evaluate ACD SLA breaches for a day and fire amber/red alerts (P2.6).

Examples:
  manage.py check_queue_sla_breaches                 # yesterday, all tenants
  manage.py check_queue_sla_breaches --day 2026-06-03 --company-id 2
Ongoing runs come from the celery-beat task acd.tasks.check_queue_sla_breaches.
"""
from django.core.management.base import BaseCommand

from acd.tasks import check_queue_sla_breaches


class Command(BaseCommand):
    help = 'Evaluate real ACD queue KPIs against thresholds and fire SLA-breach alerts'

    def add_arguments(self, parser):
        parser.add_argument('--day', help='YYYY-MM-DD (default: yesterday)')
        parser.add_argument('--company-id', type=int)

    def handle(self, *args, **o):
        stats = check_queue_sla_breaches(company_id=o['company_id'], day=o['day'])
        self.stdout.write(self.style.SUCCESS(
            f"{stats['breaches']} breaches, {stats['new']} new, {stats['emailed']} emailed"))
