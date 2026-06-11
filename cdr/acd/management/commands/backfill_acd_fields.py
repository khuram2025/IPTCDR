from django.core.management.base import BaseCommand

from acd.derivations import enrich_call_record
from cdr3cx.models import CallRecord


class Command(BaseCommand):
    help = 'Backfill direction, wait_time, abandoned, call_disposition on CallRecord rows'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=2000)
        parser.add_argument('--company-id', type=int)
        parser.add_argument('--last-id', type=int, default=0)

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        last_id = options['last_id']
        total = 0

        while True:
            qs = CallRecord.objects.filter(id__gt=last_id).order_by('id')
            if options['company_id']:
                qs = qs.filter(company_id=options['company_id'])
            batch = list(qs[:batch_size])
            if not batch:
                break

            for record in batch:
                enrich_call_record(record)
                if not record.ingest_transport:
                    record.ingest_transport = 'socket'

            CallRecord.objects.bulk_update(
                batch,
                ['direction', 'ring_time', 'wait_time', 'abandoned',
                 'call_disposition', 'ingest_transport'],
                batch_size=500,
            )
            total += len(batch)
            last_id = batch[-1].id
            self.stdout.write(f'Backfilled through id={last_id} ({total} rows)')

        self.stdout.write(self.style.SUCCESS(f'Done — {total} records enriched'))
