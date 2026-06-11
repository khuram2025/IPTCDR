from django.core.management.base import BaseCommand
from django.db.models import Count

from accounts.models import Company, Extension
from acd.models import Agent
from cdr3cx.models import CallRecord
from cdr3cx.callcenter_filters import answered_call_filter


class Command(BaseCommand):
    help = 'Seed Agent profiles from Extension records and call-center answered calls'

    def handle(self, *args, **options):
        for company in Company.objects.all():
            created = 0
            for ext in Extension.objects.filter(company=company):
                name = ext.full_name or ext.first_name or f'Ext {ext.extension}'
                _, was_created = Agent.objects.get_or_create(
                    company=company,
                    source_pbx='3cx',
                    external_id=ext.extension,
                    defaults={
                        'extension': ext,
                        'display_name': name[:128],
                    },
                )
                if was_created:
                    created += 1

            # Also pick up agents seen in CDR but missing from Extension table
            agents_from_cdr = (
                CallRecord.objects.filter(company=company)
                .filter(answered_call_filter())
                .exclude(final_dn__isnull=True)
                .exclude(final_dn='')
                .values('final_dn', 'final_dispname')
                .annotate(calls=Count('id'))
                .order_by('-calls')[:100]
            )
            for row in agents_from_cdr:
                dn = row['final_dn']
                name = row['final_dispname'] or f'Ext {dn}'
                _, was_created = Agent.objects.get_or_create(
                    company=company,
                    source_pbx='3cx',
                    external_id=dn,
                    defaults={'display_name': name[:128]},
                )
                if was_created:
                    created += 1

            self.stdout.write(self.style.SUCCESS(f'{company.name}: {created} new agents'))
