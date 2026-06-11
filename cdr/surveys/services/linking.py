"""Link survey responses to CallRecord rows."""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from cdr3cx.models import CallRecord
from acd.models import Agent, Queue


def _normalize_phone(value: str) -> str:
    if not value:
        return ''
    return ''.join(c for c in value if c.isdigit() or c == '+')


def link_call_record(company, caller, completed_at, *,
                     call_record_id=None, correlation_id=None,
                     agent_dn=None, queue_dn=None, window_minutes=30):
    """Return (call_record, agent, queue, match_confidence)."""
    if call_record_id:
        try:
            rec = CallRecord.objects.select_related('agent', 'queue').get(
                pk=call_record_id, company=company,
            )
            return rec, rec.agent, rec.queue, 'exact'
        except CallRecord.DoesNotExist:
            pass

    if correlation_id:
        rec = (
            CallRecord.objects.filter(company=company, correlation_id=correlation_id)
            .select_related('agent', 'queue')
            .order_by('-call_time')
            .first()
        )
        if rec:
            return rec, rec.agent, rec.queue, 'exact'

    if not caller or not completed_at:
        agent, queue = _resolve_hints(company, agent_dn, queue_dn)
        return None, agent, queue, 'unmatched'

    if timezone.is_naive(completed_at):
        completed_at = timezone.make_aware(completed_at, timezone.get_current_timezone())

    window_start = completed_at - timedelta(minutes=window_minutes)
    norm = _normalize_phone(caller)
    qs = (
        CallRecord.objects.filter(
            company=company,
            call_time__lte=completed_at,
            call_time__gte=window_start,
            time_answered__isnull=False,
        )
        .select_related('agent', 'queue')
        .order_by('-call_time')
    )

    if norm:
        qs = qs.filter(
            Q(from_no__icontains=norm[-10:]) | Q(caller__icontains=norm[-10:])
            if len(norm) >= 10 else (Q(from_no=caller) | Q(caller=caller))
        )

    if agent_dn:
        qs = qs.filter(final_dn=agent_dn)
    if queue_dn:
        qs = qs.filter(Q(to_dn=queue_dn) | Q(final_dn=queue_dn))

    rec = qs.first()
    if rec:
        return rec, rec.agent, rec.queue, 'heuristic'

    agent, queue = _resolve_hints(company, agent_dn, queue_dn)
    return None, agent, queue, 'unmatched'


def _resolve_hints(company, agent_dn, queue_dn):
    agent = None
    queue = None
    if agent_dn:
        agent = Agent.objects.filter(company=company, external_id=agent_dn).first()
    if queue_dn:
        queue = Queue.objects.filter(company=company, external_id=queue_dn).first()
    return agent, queue
