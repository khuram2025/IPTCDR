"""KPI snapshot service.

Builds the dashboard payload from current data — sent to wallboard clients
on connect and on each call event so a freshly-opened browser doesn't have
to wait for the next CDR to populate.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from cdr3cx.models import CallRecord


def build(company, *, hours: int = 24) -> dict:
    """Return a dict suitable for direct JSON serialization to a wallboard."""
    if company is None:
        return {}

    now = timezone.now()
    window_start = now - timedelta(hours=hours)

    # Base queryset for the window
    qs = CallRecord.objects.filter(company=company, call_time__gte=window_start)

    # Top-level counters
    counts = qs.aggregate(
        total=Count('id'),
        answered=Count('id', filter=~Q(reason_terminated='NoAnswer') & ~Q(duration=None)),
        missed=Count('id', filter=Q(reason_terminated='NoAnswer')),
        total_duration=Sum('duration'),
        total_cost=Sum('total_cost'),
        avg_duration=Avg('duration'),
    )
    answered = counts['answered'] or 0
    total = counts['total'] or 0
    answer_rate = round((answered / total) * 100, 1) if total else 0

    # Calls in progress (last 5 min, no end yet)
    in_progress = CallRecord.objects.filter(
        company=company,
        call_time__gte=now - timedelta(minutes=10),
        time_end__isnull=True,
    ).count()

    # Recent calls ticker (last 10)
    recent = list(
        CallRecord.objects.filter(company=company)
        .order_by('-call_time')[:10]
        .values('id', 'caller', 'callee', 'duration', 'call_time',
                'from_dispname', 'to_dispname', 'call_category', 'total_cost')
    )
    for r in recent:
        r['call_time'] = r['call_time'].isoformat() if r['call_time'] else None
        r['total_cost'] = str(r['total_cost']) if r['total_cost'] is not None else None

    # Hourly histogram (last 24h)
    hourly = [0] * 24
    for r in qs.values('call_time').iterator():
        ct = r['call_time']
        if ct:
            hourly[ct.hour] += 1

    return {
        'as_of': now.isoformat(),
        'window_hours': hours,
        'counters': {
            'total':         total,
            'answered':      answered,
            'missed':        counts['missed'] or 0,
            'in_progress':   in_progress,
            'answer_rate':   answer_rate,
            'avg_duration':  round(counts['avg_duration'] or 0, 1),
            'total_duration': counts['total_duration'] or 0,
            'total_cost':    str(counts['total_cost'] or Decimal('0')),
        },
        'hourly': hourly,
        'recent': recent,
    }


def build_heatmap(company, *, days: int = 7) -> dict:
    """7×24 grid of call counts by day-of-week × hour-of-day for last ``days``."""
    if company is None:
        return {'grid': [[0]*24 for _ in range(7)], 'days': days}
    since = timezone.now() - timedelta(days=days)
    grid = [[0]*24 for _ in range(7)]
    qs = CallRecord.objects.filter(
        company=company, call_time__gte=since,
    ).values_list('call_time', flat=True)
    for ct in qs.iterator():
        if ct:
            grid[ct.weekday()][ct.hour] += 1
    return {'grid': grid, 'days': days, 'as_of': timezone.now().isoformat()}
