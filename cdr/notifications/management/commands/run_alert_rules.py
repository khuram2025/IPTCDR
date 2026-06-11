"""Evaluate the alert-rules engine once (P4.4).

  manage.py run_alert_rules
"""
from django.core.management.base import BaseCommand

from notifications.alert_engine import run_all


class Command(BaseCommand):
    help = 'Evaluate tenant alert rules across all sources and dispatch + escalate'

    def handle(self, *args, **o):
        res = run_all()
        self.stdout.write(self.style.SUCCESS(
            f"fraud={res['fraud']} acd_sla={res['acd_sla']} escalated={res['escalated']}"))
