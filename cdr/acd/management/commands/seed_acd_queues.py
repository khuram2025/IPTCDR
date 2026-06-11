from django.core.management.base import BaseCommand
from django.db.models import Count

from accounts.models import Company
from acd.models import Queue, ThresholdPolicy
from cdr3cx.models import CallRecord
from cdr3cx.callcenter_filters import call_center_call_filter


class Command(BaseCommand):
    help = 'Seed Queue entities from distinct IVR to_dn values in CallRecord history'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, help='Limit to one company')

    def handle(self, *args, **options):
        companies = Company.objects.all()
        if options['company_id']:
            companies = companies.filter(pk=options['company_id'])

        for company in companies:
            ivrs = (
                CallRecord.objects.filter(company=company)
                .filter(call_center_call_filter())
                .exclude(to_dn__isnull=True)
                .exclude(to_dn='')
                .values('to_dn', 'to_dispname')
                .annotate(calls=Count('id'))
                .order_by('-calls')
            )
            created = 0
            for row in ivrs:
                dn = row['to_dn']
                name = row['to_dispname'] or f'IVR {dn}'
                _, was_created = Queue.objects.get_or_create(
                    company=company,
                    source_pbx='3cx',
                    external_id=dn,
                    defaults={'name': name[:128]},
                )
                if was_created:
                    created += 1

            ThresholdPolicy.objects.get_or_create(
                company=company,
                queue=None,
                defaults={
                    'sla_target_seconds': 20,
                    'sla_target_pct': 80,
                    'short_abandon_seconds': 10,
                },
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'{company.name}: seeded {created} new queues ({ivrs.count()} IVR DNs total)'
                )
            )
