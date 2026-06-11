"""Materialized daily rollups (P3.5).

build_call_rollups recomputes CallDailyRollup rows from CallRecord (idempotent
upsert per company/day) using the SAME case-insensitive call-center filters as the
dashboard, so the rollup always reconciles with a live query. rollup_daily_map
reads them back in the shape _build_daily_trends expects, letting the dashboard
serve date-range trends without scanning the full CallRecord table.
"""
import logging
from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from cdr3cx.callcenter_filters import (
    call_center_call_filter, answered_call_filter, missed_call_filter,
)

logger = logging.getLogger(__name__)


def build_call_rollups(company_id=None, days_back=400):
    """Rebuild CallDailyRollup for the recent window. Returns rows upserted."""
    from accounts.models import Company
    from cdr3cx.models import CallRecord
    from acd.models import CallDailyRollup

    companies = Company.objects.all()
    if company_id:
        companies = companies.filter(pk=company_id)

    today = timezone.localdate()
    floor = today - timedelta(days=days_back)
    upserts = 0
    for company in companies:
        agg = {
            r['day']: r
            for r in CallRecord.objects.filter(company=company, call_time__date__gte=floor)
            .filter(call_center_call_filter())
            .annotate(day=TruncDate('call_time'))
            .values('day')
            .annotate(
                cc_total=Count('id'),
                cc_answered=Count('id', filter=answered_call_filter()),
                cc_missed=Count('id', filter=missed_call_filter()),
                talk=Sum('duration', filter=answered_call_filter()),
            )
            if r['day']
        }
        # Upsert a row for EVERY day in the window (zeros where no activity) so
        # rollup_daily_map can tell "covered + zero" from "not built yet".
        d = floor
        while d <= today:
            r = agg.get(d, {})
            CallDailyRollup.objects.update_or_create(
                company=company, day=d,
                defaults={
                    'cc_total': r.get('cc_total') or 0,
                    'cc_answered': r.get('cc_answered') or 0,
                    'cc_missed': r.get('cc_missed') or 0,
                    'total_talk_seconds': int(r.get('talk') or 0),
                    'source': 'callrecord',
                },
            )
            upserts += 1
            d += timedelta(days=1)
    if upserts:
        logger.info('build_call_rollups upserted %s company-day rows', upserts)
    return upserts


def rollup_daily_map(company, start_date, end_date):
    """{date: {'total_calls','answered_calls','missed_calls'}} from rollups, or
    None when the window is not fully covered (caller should fall back to live)."""
    from acd.models import CallDailyRollup

    sd = start_date.date() if hasattr(start_date, 'date') else start_date
    ed = end_date.date() if hasattr(end_date, 'date') else end_date
    rows = {
        r.day: r for r in CallDailyRollup.objects.filter(
            company=company, day__range=[sd, ed])
    }
    # Require coverage up to *yesterday* (today is still accumulating live).
    needed_end = min(ed, timezone.localdate() - timedelta(days=1))
    d = sd
    while d <= needed_end:
        if d not in rows:
            return None  # gap → let the caller compute live for accuracy
        d += timedelta(days=1)
    return {
        day: {
            'total_calls': r.cc_total,
            'answered_calls': r.cc_answered,
            'missed_calls': r.cc_missed,
        } for day, r in rows.items()
    }
