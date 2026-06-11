"""Live supervisor wallboard snapshot (P2.4).

Builds the real-time operational picture for a tenant's ACD from the 3CX XAPI
``ActiveCalls`` feed (live calls now) merged with today's pulled QueueDailyStats /
abandonment / open SLA alerts (DB, cheap). The live part is cached briefly so many
supervisors watching the board hit the PBX XAPI at most once per refresh window.

Unlike the dashboards (which look back over a date range), this answers "what is
happening right now": calls talking, calls waiting, the longest current wait, and
per-queue live load — the numbers a supervisor acts on minute to minute.
"""
import re
import logging
from datetime import datetime, timezone as dt_tz

from django.core.cache import cache
from django.utils import timezone

from acd.kpi import format_seconds

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 5
_TALKING = 'Talking'


def _parse_iso(s):
    """Parse a 3CX ISO timestamp (handles 'Z' and 7-digit fractional seconds)."""
    if not s:
        return None
    s = s.strip()
    s = re.sub(r'(\.\d{6})\d+', r'\1', s)  # trim >6 fractional digits
    s = s.replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_tz.utc)
    return dt


def _client(company):
    from acd.sources.threecx_xapi import ThreeCXXapiClient
    if not (company.pbx_api_url and company.pbx_api_user and company.pbx_api_password):
        return None
    return ThreeCXXapiClient(
        company.pbx_api_url, company.pbx_api_user, company.pbx_api_password,
        verify_tls=True, timeout=15,
    )


def _live_calls(company, queues):
    """Fetch + classify live calls. Returns the 'live' sub-dict (or an error one).

    queues: {dn: name} for the company's ACD queues, used to tag a call as
    belonging to a queue when its caller/callee references the DN or name.
    """
    client = _client(company)
    if client is None:
        return {'ok': False, 'error': 'No PBX API configured', 'active_total': 0,
                'talking': 0, 'connecting': 0, 'longest_wait_seconds': None,
                'longest_wait_formatted': '—', 'calls': []}
    try:
        raw = client.active_calls()
    except Exception as e:
        logger.warning('wallboard: ActiveCalls failed for %s: %s', company.name, e)
        return {'ok': False, 'error': 'PBX unreachable', 'active_total': 0,
                'talking': 0, 'connecting': 0, 'longest_wait_seconds': None,
                'longest_wait_formatted': '—', 'calls': []}

    needles = []  # (lowercased token, dn) to match a call to a queue
    for dn, name in queues.items():
        needles.append((dn.lower(), dn))
        if name:
            needles.append((name.lower(), dn))

    talking = connecting = 0
    longest_wait = None
    calls = []
    for c in raw:
        now = _parse_iso(c['server_now']) or timezone.now()
        est = _parse_iso(c['established_at'])
        chg = _parse_iso(c['last_change']) or est
        age = int((now - est).total_seconds()) if est else None          # total call age
        state_age = int((now - chg).total_seconds()) if chg else age      # time in current state
        is_talking = (c['status'] == _TALKING)

        hay = f"{c['caller']} {c['callee']}".lower()
        queue_dn = next((dn for token, dn in needles if token and token in hay), None)

        if is_talking:
            talking += 1
        else:
            connecting += 1
            if state_age is not None and (longest_wait is None or state_age > longest_wait):
                longest_wait = state_age

        calls.append({
            'id': c['id'], 'caller': c['caller'][:60], 'callee': c['callee'][:60],
            'status': c['status'], 'queue_dn': queue_dn,
            'waiting': not is_talking,
            'age_seconds': age, 'age_formatted': format_seconds(age),
            'state_age_seconds': state_age,
        })

    # Waiting first, then longest-waiting at the top.
    calls.sort(key=lambda x: (not x['waiting'], -(x['state_age_seconds'] or 0)))
    return {
        'ok': True, 'error': '',
        'active_total': len(raw), 'talking': talking, 'connecting': connecting,
        'longest_wait_seconds': longest_wait,
        'longest_wait_formatted': format_seconds(longest_wait),
        'calls': calls[:25],
    }


def _today_rollup(company, queues, today):
    """DB-only: today's QueueDailyStats + abandonment + per-queue live-ready rows."""
    from django.db.models import Sum
    from acd.models import QueueDailyStats, QueueAbandonedCall

    qds = QueueDailyStats.objects.filter(
        queue__company=company, queue__is_acd_queue=True, stat_date=today)
    agg = qds.aggregate(c=Sum('calls'), a=Sum('answered'), ring=Sum('ring_time_seconds'))
    calls, answered = agg['c'] or 0, agg['a'] or 0
    asa = round(agg['ring'] / calls, 1) if agg['ring'] and calls else None
    abandoned_today = QueueAbandonedCall.objects.filter(
        queue__company=company, queue__is_acd_queue=True, call_time__date=today).count()

    per_q = {}
    for r in (qds.values('queue__external_id', 'queue__name')
              .annotate(c=Sum('calls'), a=Sum('answered'), ring=Sum('ring_time_seconds'))):
        dn = r['queue__external_id']
        c, a = r['c'] or 0, r['a'] or 0
        per_q[dn] = {
            'name': r['queue__name'], 'dn': dn,
            'calls_today': c, 'answered_today': a, 'abandoned_today': max(0, c - a),
            'answer_rate_today': round(a / c * 100, 1) if c else None,
            'asa_today_seconds': round(r['ring'] / c, 1) if r['ring'] and c else None,
        }
    today_block = {
        'offered': calls, 'answered': answered, 'abandoned': max(0, calls - answered),
        'answer_rate': round(answered / calls * 100, 1) if calls else None,
        'asa_seconds': asa, 'asa_formatted': format_seconds(asa),
        'abandoned_today': abandoned_today,
    }
    return today_block, per_q


def _open_alert_counts(company, today):
    """Red/amber SLA-alert counts for today + yesterday (the 'live' breach badge)."""
    from datetime import timedelta
    from django.db.models import Count
    from acd.models import QueueAlert
    rows = (QueueAlert.objects.filter(
        queue__company=company, stat_date__gte=today - timedelta(days=1))
        .values('severity').annotate(n=Count('id')))
    counts = {'red': 0, 'amber': 0}
    for r in rows:
        counts[r['severity']] = r['n']
    return counts


def wallboard_snapshot(company, *, use_cache=True):
    """Full wallboard snapshot for a company. Live part cached CACHE_TTL_SECONDS."""
    key = f'wallboard:{company.id}'
    if use_cache:
        cached = cache.get(key)
        if cached is not None:
            return cached

    from acd.models import Queue
    queues = {
        q.external_id: q.name
        for q in Queue.objects.filter(company=company, is_acd_queue=True)
    }
    today = timezone.localdate()

    live = _live_calls(company, queues)
    today_block, per_q = _today_rollup(company, queues, today)

    # Merge live waiting counts into the per-queue rows.
    waiting_by_dn = {}
    for c in live['calls']:
        if c['waiting'] and c['queue_dn']:
            waiting_by_dn[c['queue_dn']] = waiting_by_dn.get(c['queue_dn'], 0) + 1
    per_queue = []
    for dn, name in queues.items():
        row = per_q.get(dn, {
            'name': name, 'dn': dn, 'calls_today': 0, 'answered_today': 0,
            'abandoned_today': 0, 'answer_rate_today': None, 'asa_today_seconds': None,
        })
        row['waiting_now'] = waiting_by_dn.get(dn, 0)
        per_queue.append(row)
    per_queue.sort(key=lambda r: (-r['waiting_now'], -r['calls_today']))

    snapshot = {
        'ok': live['ok'],
        'error': live['error'],
        'as_of': timezone.now().isoformat(),
        'company': company.name,
        'live': live,
        'today': today_block,
        'per_queue': per_queue,
        'alerts': _open_alert_counts(company, today),
    }
    cache.set(key, snapshot, CACHE_TTL_SECONDS)
    return snapshot
