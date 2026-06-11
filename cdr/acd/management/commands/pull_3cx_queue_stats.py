"""Pull 3CX queue daily stats via the XAPI into QueueDailyStats.

Backfill example:  manage.py pull_3cx_queue_stats --days-back 120
Ongoing is handled by the celery-beat task (default days_back=2).
"""
from django.core.management.base import BaseCommand

from acd.tasks import pull_3cx_queue_stats


class Command(BaseCommand):
    help = 'Pull per-queue daily ACD stats from the 3CX XAPI into QueueDailyStats'

    def add_arguments(self, parser):
        parser.add_argument('--days-back', type=int, default=90)
        parser.add_argument('--company-id', type=int)
        parser.add_argument('--no-verify-tls', action='store_true',
                            help='Disable TLS verification (self-signed 3CX certs)')

    def handle(self, *args, **o):
        summary = pull_3cx_queue_stats(
            company_id=o['company_id'],
            days_back=o['days_back'],
            verify_tls=not o['no_verify_tls'],
        )
        self.stdout.write(self.style.SUCCESS(
            f"Upserted {summary['queue_days']} queue-day, "
            f"{summary['abandoned']} abandoned-call, "
            f"{summary['agent_days']} agent-day rows"))
