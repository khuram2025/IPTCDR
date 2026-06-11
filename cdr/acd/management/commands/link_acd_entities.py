"""One-time historical backfill: link CallRecords to seeded Queue/Agent rows.

The derived ACD columns (direction/wait_time/abandoned/call_disposition) were
already backfilled; this fills the queue_id/agent_id FKs that were left NULL.
Single forward pass keyed on id (resumable via --last-id), so non-matching rows
are visited once and never re-scanned.
"""
from django.core.management.base import BaseCommand

from acd.models import Queue, Agent
from cdr3cx.models import CallRecord


class Command(BaseCommand):
    help = 'Backfill queue_id/agent_id on CallRecord from to_dn/final_dn'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=5000)
        parser.add_argument('--last-id', type=int, default=0)
        parser.add_argument('--company-id', type=int)

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        last_id = options['last_id']
        total = linked_q = linked_a = 0

        # Preload tiny lookup maps once (18 queues, ~900 agents) so the pass over
        # 1.49M rows does zero per-row queries.
        queues = {(c, e): i for c, e, i in Queue.objects.values_list('company_id', 'external_id', 'id')}
        agents = {(c, e): i for c, e, i in Agent.objects.values_list('company_id', 'external_id', 'id')}

        while True:
            qs = CallRecord.objects.filter(id__gt=last_id).order_by('id')
            if options['company_id']:
                qs = qs.filter(company_id=options['company_id'])
            batch = list(qs.only('id', 'company_id', 'to_dn', 'final_dn')[:batch_size])
            if not batch:
                break

            for rec in batch:
                rec.queue_id = queues.get((rec.company_id, (rec.to_dn or '').strip()))
                rec.agent_id = agents.get((rec.company_id, (rec.final_dn or '').strip()))
                linked_q += 1 if rec.queue_id else 0
                linked_a += 1 if rec.agent_id else 0

            CallRecord.objects.bulk_update(batch, ['queue_id', 'agent_id'], batch_size=1000)
            total += len(batch)
            last_id = batch[-1].id
            if total % 100000 == 0:
                self.stdout.write(f'  ...{total} scanned (queue={linked_q} agent={linked_a}) id<={last_id}')

        self.stdout.write(self.style.SUCCESS(
            f'Done — scanned {total}; linked queue={linked_q}, agent={linked_a}'
        ))
