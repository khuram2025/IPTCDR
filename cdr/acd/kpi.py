"""ACD KPI computation from CallRecord data."""
from django.db.models import (
    Avg, Case, Count, F, Max, Q, Value, When,
    ExpressionWrapper, DurationField, IntegerField,
)
from django.db.models.functions import Coalesce, Extract

from cdr3cx.callcenter_filters import call_center_call_filter, missed_call_filter


def get_threshold_policy(company, queue=None):
    from acd.models import ThresholdPolicy
    if queue:
        policy = ThresholdPolicy.objects.filter(
            company=company, queue=queue, is_active=True,
        ).first()
        if policy:
            return policy
    return ThresholdPolicy.objects.filter(
        company=company, queue__isnull=True, is_active=True,
    ).first()


def default_sla_seconds(company, queue=None):
    policy = get_threshold_policy(company, queue)
    if policy:
        return policy.sla_target_seconds, policy.sla_target_pct, policy.short_abandon_seconds
    return 20, 80, 10


def _annotate_effective_wait(qs):
    """Use stored wait_time when present; otherwise derive from timestamps."""
    answered_wait = ExpressionWrapper(
        Extract(F('time_answered') - F('call_time'), 'epoch'),
        output_field=IntegerField(),
    )
    abandoned_wait = ExpressionWrapper(
        Extract(F('time_end') - F('call_time'), 'epoch'),
        output_field=IntegerField(),
    )
    return qs.annotate(
        computed_wait=Case(
            When(time_answered__isnull=False, then=answered_wait),
            When(time_end__isnull=False, then=abandoned_wait),
            default=Value(None),
            output_field=IntegerField(),
        ),
        effective_wait=Coalesce('wait_time', 'computed_wait'),
    )


def compute_queue_kpis(qs, *, sla_seconds=20, short_abandon_seconds=10, wait_reliable=False):
    """Compute Service Level, ASA, abandonment from a CallRecord queryset."""
    qs = _annotate_effective_wait(qs)

    answered_q = Q(time_answered__isnull=False)
    abandoned_q = missed_call_filter()
    short_abandon_q = abandoned_q & Q(effective_wait__lte=short_abandon_seconds)
    within_sla_q = answered_q & Q(effective_wait__lte=sla_seconds)

    agg = qs.aggregate(
        offered=Count('id'),
        answered=Count('id', filter=answered_q),
        abandoned=Count('id', filter=abandoned_q),
        short_abandon=Count('id', filter=short_abandon_q),
        within_sla=Count('id', filter=within_sla_q),
        asa_seconds=Avg('effective_wait', filter=answered_q),
        avg_wait=Avg('effective_wait'),
        longest_wait=Max('effective_wait'),
        avg_talk=Avg('duration', filter=answered_q),
    )

    answered = agg['answered'] or 0
    abandoned = agg['abandoned'] or 0
    denominator = answered + abandoned
    abandon_rate = round(abandoned / denominator * 100, 1) if denominator else 0
    answer_rate = round(answered / (agg['offered'] or 1) * 100, 1)

    # Wait-based KPIs (Service Level, ASA, wait times, short-abandon) are only
    # meaningful when the feed carries real agent-wait timing. The 3CX active-socket
    # CDR does NOT — time_answered is the system/IVR auto-answer instant (~0s for
    # every final_type, verified live) — so they are suppressed (None) unless an
    # authoritative queue feed sets wait_reliable=True. See roadmap P1.3 (3CX queue
    # DB-pull) and the acd-data-limit note.
    if wait_reliable:
        within_sla = agg['within_sla'] or 0
        wait_kpis = {
            'service_level': round(within_sla / denominator * 100, 1) if denominator else 0,
            'within_sla': within_sla,
            'short_abandon': agg['short_abandon'] or 0,
            'asa_seconds': round(agg['asa_seconds'] or 0, 1),
            'avg_wait_seconds': round(agg['avg_wait'] or 0, 1),
            'longest_wait_seconds': int(agg['longest_wait'] or 0),
        }
    else:
        wait_kpis = {
            'service_level': None, 'within_sla': None, 'short_abandon': None,
            'asa_seconds': None, 'avg_wait_seconds': None, 'longest_wait_seconds': None,
        }

    return {
        'offered': agg['offered'] or 0,
        'answered': answered,
        'abandoned': abandoned,
        'abandon_rate': abandon_rate,
        'answer_rate': answer_rate,
        'avg_talk_seconds': round(agg['avg_talk'] or 0, 1),
        'sla_seconds': sla_seconds,
        'wait_metrics_available': wait_reliable,
        **wait_kpis,
    }


def compute_company_callcenter_kpis(company, start, end):
    """KPIs for the call-center dashboard date window."""
    from cdr3cx.models import CallRecord

    sla_seconds, sla_pct, short_abandon = default_sla_seconds(company)
    qs = CallRecord.objects.filter(
        company=company,
        call_time__range=[start, end],
    ).filter(call_center_call_filter())

    # wait_reliable stays False for the 3CX socket feed (no real agent-wait timing);
    # flip to True when sourcing from the 3CX queue CDR (P1.3) per company/queue.
    return compute_queue_kpis(
        qs, sla_seconds=sla_seconds, short_abandon_seconds=short_abandon,
        wait_reliable=False,
    )


def format_seconds(seconds):
    if seconds is None:
        return '—'
    seconds = int(seconds)
    minutes, secs = divmod(seconds, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def real_queue_kpis(company, start, end):
    """GENUINE ACD KPIs from 3CX XAPI QueueDailyStats (real agent-wait timing).

    Unlike compute_company_callcenter_kpis (socket feed, wait suppressed), this
    has real RingTime, so ASA/answer-rate/abandonment are trustworthy. 3CX's
    AvgRingTime == total RingTime / total calls, so ASA = ring_time / calls.
    Returns aggregate KPIs + a per-queue breakdown; `available` is False when no
    queue stats have been pulled for the window.
    """
    from django.db.models import Sum
    from acd.models import QueueDailyStats, QueueAbandonedCall

    sd = start.date() if hasattr(start, 'date') else start
    ed = end.date() if hasattr(end, 'date') else end
    rows = QueueDailyStats.objects.filter(
        queue__company=company, queue__is_acd_queue=True, stat_date__range=[sd, ed],
    )

    # Real abandonment detail (true wait-before-abandon), per queue DN.
    short_abandon_seconds = default_sla_seconds(company)[2]
    ab_rows = QueueAbandonedCall.objects.filter(
        queue__company=company, queue__is_acd_queue=True, call_time__date__range=[sd, ed],
    )
    ab_by_dn = {}
    for r in (ab_rows.values('queue__external_id')
              .annotate(n=Count('id'), avg_wait=Avg('wait_seconds'),
                        max_wait=Max('wait_seconds'),
                        short=Count('id', filter=Q(wait_seconds__lte=short_abandon_seconds)))):
        ab_by_dn[r['queue__external_id']] = r

    def _asa(ring, calls):
        return round(ring / calls, 1) if ring is not None and calls else None

    per_queue = []
    for r in (rows.values('queue__name', 'queue__external_id')
              .annotate(c=Sum('calls'), a=Sum('answered'),
                        ring=Sum('ring_time_seconds'), talk=Sum('talk_time_seconds'))
              .order_by('-c')):
        c, a = r['c'] or 0, r['a'] or 0
        ab = ab_by_dn.get(r['queue__external_id'], {})
        per_queue.append({
            'name': r['queue__name'], 'dn': r['queue__external_id'],
            'calls': c, 'answered': a, 'abandoned': max(0, c - a),
            'answer_rate': round(a / c * 100, 1) if c else 0,
            'abandon_rate': round((c - a) / c * 100, 1) if c else 0,
            'asa_seconds': _asa(r['ring'], c),
            'avg_talk_seconds': _asa(r['talk'], a),
            'abandon_count': ab.get('n', 0),
            'avg_abandon_wait_seconds': round(ab['avg_wait'], 1) if ab.get('avg_wait') else None,
            'max_abandon_wait_seconds': int(ab['max_wait']) if ab.get('max_wait') else None,
            'short_abandons': ab.get('short', 0),
        })

    agg = rows.aggregate(c=Sum('calls'), a=Sum('answered'), ring=Sum('ring_time_seconds'))
    calls, answered = agg['c'] or 0, agg['a'] or 0
    ab_agg = ab_rows.aggregate(
        n=Count('id'), avg_wait=Avg('wait_seconds'), max_wait=Max('wait_seconds'),
        short=Count('id', filter=Q(wait_seconds__lte=short_abandon_seconds)))
    return {
        'available': bool(per_queue),
        'wait_metrics_available': True,
        'calls': calls, 'answered': answered, 'abandoned': max(0, calls - answered),
        'answer_rate': round(answered / calls * 100, 1) if calls else 0,
        'abandon_rate': round((calls - answered) / calls * 100, 1) if calls else 0,
        'asa_seconds': _asa(agg['ring'], calls),
        'abandon_count': ab_agg['n'] or 0,
        'avg_abandon_wait_seconds': round(ab_agg['avg_wait'], 1) if ab_agg['avg_wait'] else None,
        'max_abandon_wait_seconds': int(ab_agg['max_wait']) if ab_agg['max_wait'] else None,
        'short_abandons': ab_agg['short'] or 0,
        'short_abandon_seconds': short_abandon_seconds,
        'per_queue': per_queue,
    }


def agent_productivity(company, start, end):
    """Per-agent productivity from 3CX XAPI AgentQueueDailyStats (real agent-side
    timing the socket CDR lacks): answered vs lost rings, answer rate, talk time,
    and an occupancy proxy (talk / logged-in). Aggregated across the tenant's ACD
    queues for the window. `available` is False when no agent stats were pulled.
    """
    from django.db.models import Sum
    from acd.models import AgentQueueDailyStats

    sd = start.date() if hasattr(start, 'date') else start
    ed = end.date() if hasattr(end, 'date') else end
    rows = AgentQueueDailyStats.objects.filter(
        queue__company=company, queue__is_acd_queue=True, stat_date__range=[sd, ed],
    )

    agents = []
    for r in (rows.values('agent_dn', 'agent_name')
              .annotate(ans=Sum('answered'), lost=Sum('lost'),
                        talk=Sum('talk_time_seconds'), li=Sum('logged_in_seconds'))
              .order_by('-ans', 'agent_name')):
        ans, lost = r['ans'] or 0, r['lost'] or 0
        rings = ans + lost
        li, tk = r['li'] or 0, r['talk'] or 0
        # Only surface agents who showed any activity or availability in the window.
        if not (ans or lost or li):
            continue
        agents.append({
            'dn': r['agent_dn'], 'name': r['agent_name'] or r['agent_dn'],
            'answered': ans, 'lost': lost,
            'answer_rate': round(ans / rings * 100, 1) if rings else None,
            'talk_seconds': tk, 'logged_in_seconds': li,
            'avg_talk_seconds': round(tk / ans, 1) if ans else None,
            'occupancy_pct': round(tk / li * 100, 1) if li else None,
        })

    agg = rows.aggregate(ans=Sum('answered'), lost=Sum('lost'))
    return {
        'available': bool(agents),
        'agents': agents,
        'agent_count': len(agents),
        'total_answered': agg['ans'] or 0,
        'total_lost': agg['lost'] or 0,
    }


def agent_acd_detail(company, agent_dn, start, end):
    """One agent's real ACD performance from AgentQueueDailyStats (P2.5).

    The per-agent drill-down: answered vs lost rings + answer rate (paired to the
    tenant SLA target), AHT (talk / answered), occupancy (talk / logged-in), and a
    per-queue split — all real agent-side timing the socket CDR can't give. Returns
    `available` False when the agent has no pulled ACD stats in the window.
    """
    from django.db.models import Sum
    from acd.models import AgentQueueDailyStats

    sd = start.date() if hasattr(start, 'date') else start
    ed = end.date() if hasattr(end, 'date') else end
    rows = AgentQueueDailyStats.objects.filter(
        queue__company=company, agent_dn=str(agent_dn), stat_date__range=[sd, ed],
    )
    if not rows.exists():
        return {'available': False}

    name = (rows.exclude(agent_name='').values_list('agent_name', flat=True).first()
            or str(agent_dn))
    agg = rows.aggregate(ans=Sum('answered'), lost=Sum('lost'),
                         talk=Sum('talk_time_seconds'), li=Sum('logged_in_seconds'))
    ans, lost = agg['ans'] or 0, agg['lost'] or 0
    rings = ans + lost
    talk, li = agg['talk'] or 0, agg['li'] or 0
    target_pct = default_sla_seconds(company)[1]
    answer_rate = round(ans / rings * 100, 1) if rings else None

    per_queue = []
    for r in (rows.values('queue__name', 'queue__external_id')
              .annotate(a=Sum('answered'), l=Sum('lost'),
                        tk=Sum('talk_time_seconds'), liq=Sum('logged_in_seconds'))
              .order_by('-a')):
        a, l = r['a'] or 0, r['l'] or 0
        rr = a + l
        qtalk, qli = r['tk'] or 0, r['liq'] or 0
        per_queue.append({
            'name': r['queue__name'], 'dn': r['queue__external_id'],
            'answered': a, 'lost': l,
            'answer_rate': round(a / rr * 100, 1) if rr else None,
            'aht_seconds': round(qtalk / a, 1) if a else None,
            'occupancy_pct': round(qtalk / qli * 100, 1) if qli else None,
        })

    return {
        'available': True,
        'name': name,
        'dn': str(agent_dn),
        'answered': ans,
        'lost': lost,
        'rings': rings,
        'answer_rate': answer_rate,
        'target_pct': target_pct,
        'answer_meets_target': (answer_rate is not None and answer_rate >= target_pct),
        'aht_seconds': round(talk / ans, 1) if ans else None,
        'talk_seconds': talk,
        'logged_in_seconds': li,
        'occupancy_pct': round(talk / li * 100, 1) if li else None,
        'per_queue': per_queue,
    }
