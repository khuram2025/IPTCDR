from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum, Avg
from django.db.models.functions import ExtractHour, TruncDate
from django.utils import timezone
from datetime import datetime, timedelta
from .models import CallRecord
from .callcenter_filters import call_center_call_filter, answered_call_filter, missed_call_filter
from acd.kpi import (
    compute_company_callcenter_kpis, format_seconds, real_queue_kpis,
    agent_productivity,
)
from accounts.models import Extension
import logging

logger = logging.getLogger(__name__)


CC_PERIODS = [
    ('today', 'Today'),
    ('7d', '7D'),
    ('1m', '1M'),
    ('6m', '6M'),
    ('1y', '1Y'),
]


def _build_daily_trends(call_center_calls, start_date, end_date, daily_rows=None):
    start_day = timezone.localtime(start_date).date()
    end_day = timezone.localtime(end_date).date()
    num_days = (end_day - start_day).days + 1

    # P3.5: daily_rows may be supplied pre-aggregated from CallDailyRollup; only
    # scan CallRecord when no rollup coverage was available.
    if daily_rows is None:
        daily_rows = {
            row['day']: row
            for row in call_center_calls.annotate(day=TruncDate('call_time'))
            .values('day')
            .annotate(
                total_calls=Count('id'),
                missed_calls=Count('id', filter=missed_call_filter()),
                answered_calls=Count('id', filter=answered_call_filter()),
            )
        }

    daily_trends = []
    if num_days <= 31:
        for i in range(num_days):
            day = start_day + timedelta(days=i)
            row = daily_rows.get(day, {})
            daily_trends.append({
                'date': day.strftime('%Y-%m-%d'),
                'label': day.strftime('%m-%d'),
                'total_calls': row.get('total_calls', 0),
                'missed_calls': row.get('missed_calls', 0),
                'answered_calls': row.get('answered_calls', 0),
            })
        trend_label = f'{num_days} day{"s" if num_days != 1 else ""}'
    else:
        week_start = start_day
        while week_start <= end_day:
            week_end = min(week_start + timedelta(days=6), end_day)
            total = missed = answered = 0
            d = week_start
            while d <= week_end:
                row = daily_rows.get(d, {})
                total += row.get('total_calls', 0)
                missed += row.get('missed_calls', 0)
                answered += row.get('answered_calls', 0)
                d += timedelta(days=1)
            daily_trends.append({
                'date': week_start.strftime('%Y-%m-%d'),
                'label': f"{week_start.strftime('%m/%d')}-{week_end.strftime('%m/%d')}",
                'total_calls': total,
                'missed_calls': missed,
                'answered_calls': answered,
            })
            week_start += timedelta(days=7)
        trend_label = 'Weekly'

    return daily_trends, trend_label


def _filter_toolbar_context(time_period, start_date, end_date, custom_date_range, date_range_label, **extra):
    ctx = {
        'time_period': time_period,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'custom_date_range': custom_date_range,
        'date_range_label': date_range_label,
        'cc_periods': CC_PERIODS,
    }
    ctx.update(extra)
    return ctx

def _resolve_callcenter_date_range(request, default_period='1m'):
    """Quick presets (time_period) + custom ISO dates + flatpickr custom_date."""
    from .utils import get_date_range

    time_period = request.GET.get('time_period', '').strip()
    if time_period:
        return get_date_range(request)

    custom_date = request.GET.get('custom_date', '').strip()
    if custom_date and ' to ' in custom_date:
        start_date_str, end_date_str = custom_date.split(' to ', 1)
        start_date = timezone.make_aware(datetime.strptime(start_date_str.strip(), '%d %b, %Y'))
        end_date = timezone.make_aware(
            datetime.strptime(end_date_str.strip(), '%d %b, %Y').replace(hour=23, minute=59, second=59)
        )
        return start_date, end_date, 'custom', custom_date

    start_raw = request.GET.get('start_date', '').strip()
    end_raw = request.GET.get('end_date', '').strip()
    if start_raw and end_raw:
        start_date = timezone.make_aware(datetime.strptime(start_raw, '%Y-%m-%d'))
        end_date = timezone.make_aware(
            datetime.strptime(end_raw, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        )
        return start_date, end_date, 'custom', ''

    now = timezone.now()
    if default_period == 'today':
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now, 'today', ''
    days_map = {'7d': 7, '1m': 30, '6m': 182, '1y': 365}
    days = days_map.get(default_period, 30)
    return now - timedelta(days=days), now, default_period, ''


def _date_range_label(time_period, start_date, end_date, custom_date_range):
    labels = {
        'today': 'Today',
        '7d': 'Last 7 days',
        '1m': 'Last 30 days',
        '6m': 'Last 6 months',
        '1y': 'Last year',
    }
    if time_period in labels:
        return labels[time_period]
    if custom_date_range:
        return custom_date_range
    return f"{start_date.strftime('%d %b %Y')} – {end_date.strftime('%d %b %Y')}"


@login_required
def call_center_dashboard(request):
    """
    Call Center Dashboard showing:
    - Top IVR missed calls
    - Top agents who received calls  
    - Call center statistics
    """
    
    if not request.user.company:
        logger.error(f"User {request.user.email} has no company assigned!")
        context = {
            'error': 'No company assigned to user',
            'top_ivr_missed_calls': [],
            'top_agents': [],
            'total_ivr_calls': 0,
            'missed_calls': 0,
            'answered_calls': 0,
            'average_call_duration': 0,
        }
        return render(request, 'cdr/callcenter/dashboard.html', context)

    start_date, end_date, time_period, custom_date_range = _resolve_callcenter_date_range(request)
    date_range_label = _date_range_label(time_period, start_date, end_date, custom_date_range)

    # Base queryset for call center calls (IVR calls)
    call_center_calls = CallRecord.objects.filter(
        company=request.user.company,
        call_time__range=[start_date, end_date]
    ).filter(
        call_center_call_filter()
    )

    # 1. Top IVR Missed Calls
    missed_calls_query = call_center_calls.filter(
        missed_call_filter()
    )
    
    top_ivr_missed_calls = missed_calls_query.values(
        'from_no', 'to_dn', 'to_dispname'
    ).annotate(
        missed_count=Count('id')
    ).order_by('-missed_count')[:10]

    # 2. Top Agents Who Received Calls
    answered_calls_query = call_center_calls.filter(answered_call_filter()).filter(
        final_dispname__isnull=False
    ).exclude(final_dispname='')

    top_agents = answered_calls_query.values(
        'final_dispname', 'final_dn'
    ).annotate(
        calls_received=Count('id'),
        total_duration=Sum('duration'),
        avg_duration=Avg('duration')
    ).order_by('-calls_received')[:10]

    # 3. Call Center Statistics
    total_ivr_calls = call_center_calls.count()
    missed_calls = missed_calls_query.count()
    answered_calls = answered_calls_query.count()
    
    # Average call duration for answered calls
    avg_duration_seconds = answered_calls_query.aggregate(
        avg_duration=Avg('duration')
    )['avg_duration'] or 0

    # Convert to minutes:seconds format
    if avg_duration_seconds:
        avg_minutes = int(avg_duration_seconds // 60)
        avg_seconds = int(avg_duration_seconds % 60)
        average_call_duration = f"{avg_minutes}:{avg_seconds:02d}"
    else:
        average_call_duration = "0:00"

    # 4. Recent Call Center Activity
    recent_calls = call_center_calls.order_by('-call_time')[:20]

    # 5. Top IVR Performance
    top_ivr_stats = call_center_calls.values('to_dn', 'to_dispname').annotate(
        total_calls=Count('id'),
        answered_calls=Count('id', filter=answered_call_filter()),
        missed_calls=Count('id', filter=missed_call_filter()),
        total_talk_time=Sum('duration', filter=answered_call_filter()),
        avg_talk_time=Avg('duration', filter=answered_call_filter())
    ).order_by('-total_calls')[:10]

    # Calculate percentages and format data for top IVRs
    for ivr in top_ivr_stats:
        if ivr['total_calls'] > 0:
            ivr['answer_rate'] = round((ivr['answered_calls'] / ivr['total_calls']) * 100, 1)
            ivr['miss_rate'] = round((ivr['missed_calls'] / ivr['total_calls']) * 100, 1)
        else:
            ivr['answer_rate'] = 0
            ivr['miss_rate'] = 0
        
        # Format talk time
        if ivr['total_talk_time']:
            hours = ivr['total_talk_time'] // 3600
            minutes = (ivr['total_talk_time'] % 3600) // 60
            ivr['total_talk_time_formatted'] = f"{hours}h {minutes}m"
        else:
            ivr['total_talk_time_formatted'] = "0h 0m"
            
        # Format average talk time
        if ivr['avg_talk_time']:
            avg_minutes = int(ivr['avg_talk_time'] // 60)
            avg_seconds = int(ivr['avg_talk_time'] % 60)
            ivr['avg_talk_time_formatted'] = f"{avg_minutes}:{avg_seconds:02d}"
        else:
            ivr['avg_talk_time_formatted'] = "0:00"

    # 6. Hourly Distribution (single grouped query — not 24 scans)
    hourly_map = {
        row['hour']: row['calls']
        for row in call_center_calls.annotate(hour=ExtractHour('call_time'))
        .values('hour').annotate(calls=Count('id'))
    }
    hourly_calls = [
        {'hour': f"{hour:02d}:00", 'calls': hourly_map.get(hour, 0)}
        for hour in range(24)
    ]

    # 7. Daily/weekly trends for selected date range (P3.5: serve from the
    #    materialized rollup when it fully covers the window; else compute live).
    from acd.rollups import rollup_daily_map
    rollup_rows = rollup_daily_map(request.user.company, start_date, end_date)
    daily_trends, daily_trend_label = _build_daily_trends(
        call_center_calls, start_date, end_date, daily_rows=rollup_rows)

    # ACD KPIs (Service Level, ASA, Abandonment)
    acd_kpis = compute_company_callcenter_kpis(request.user.company, start_date, end_date)
    acd_kpis['asa_formatted'] = format_seconds(acd_kpis['asa_seconds'])
    acd_kpis['avg_wait_formatted'] = format_seconds(acd_kpis['avg_wait_seconds'])
    acd_kpis['longest_wait_formatted'] = format_seconds(acd_kpis['longest_wait_seconds'])
    acd_kpis['avg_talk_formatted'] = format_seconds(acd_kpis['avg_talk_seconds'])

    # Genuine ACD queue KPIs from the 3CX XAPI (real agent-wait timing), if the
    # tenant has pbx_api_* configured and stats have been pulled.
    real_queue = real_queue_kpis(request.user.company, start_date, end_date)
    real_queue['asa_formatted'] = format_seconds(real_queue['asa_seconds'])
    real_queue['avg_abandon_wait_formatted'] = format_seconds(real_queue['avg_abandon_wait_seconds'])
    real_queue['max_abandon_wait_formatted'] = format_seconds(real_queue['max_abandon_wait_seconds'])
    for q in real_queue['per_queue']:
        q['asa_formatted'] = format_seconds(q['asa_seconds'])
        q['avg_talk_formatted'] = format_seconds(q['avg_talk_seconds'])
        q['avg_abandon_wait_formatted'] = format_seconds(q['avg_abandon_wait_seconds'])
        q['max_abandon_wait_formatted'] = format_seconds(q['max_abandon_wait_seconds'])

    # Headline KPI cards: prefer the GENUINE 3CX XAPI queue data when it has been
    # pulled (real agent-wait timing) over the socket feed (wait suppressed).
    # `sla_available` stays gated on genuine per-call wait — 3CX daily aggregates
    # don't carry a Service-Level %, so that card remains honest.
    acd_kpis['sla_available'] = acd_kpis.get('wait_metrics_available', False)
    if real_queue.get('available'):
        acd_kpis['wait_metrics_available'] = True
        acd_kpis['asa_formatted'] = real_queue['asa_formatted']
        acd_kpis['avg_wait_formatted'] = real_queue.get('avg_abandon_wait_formatted') or acd_kpis['avg_wait_formatted']
        acd_kpis['abandon_rate'] = real_queue['abandon_rate']
        acd_kpis['abandoned'] = real_queue['abandon_count']
        acd_kpis['longest_wait_formatted'] = real_queue.get('max_abandon_wait_formatted') or '—'

    # Per-agent productivity (answered/lost/answer-rate/occupancy) from the XAPI.
    agent_perf = agent_productivity(request.user.company, start_date, end_date)
    for a in agent_perf['agents']:
        a['avg_talk_formatted'] = format_seconds(a['avg_talk_seconds'])
        a['talk_formatted'] = format_seconds(a['talk_seconds'])

    # Fired SLA-breach alerts (P2.6) for the window — red first, most recent first.
    from acd.models import QueueAlert
    _sd = start_date.date() if hasattr(start_date, 'date') else start_date
    _ed = end_date.date() if hasattr(end_date, 'date') else end_date
    queue_alerts = list(
        QueueAlert.objects.filter(
            queue__company=request.user.company, stat_date__range=[_sd, _ed],
        ).select_related('queue').order_by('-severity', '-stat_date')[:50]
    )
    queue_alerts_summary = {
        'total': len(queue_alerts),
        'red': sum(1 for a in queue_alerts if a.severity == 'red'),
        'amber': sum(1 for a in queue_alerts if a.severity == 'amber'),
    }

    context = {
        'acd_kpis': acd_kpis,
        'real_queue': real_queue,
        'agent_perf': agent_perf,
        'queue_alerts': queue_alerts,
        'queue_alerts_summary': queue_alerts_summary,
        'top_ivr_missed_calls': top_ivr_missed_calls,
        'top_agents': top_agents,
        'top_ivr_stats': top_ivr_stats,
        'total_ivr_calls': total_ivr_calls,
        'missed_calls': missed_calls,
        'answered_calls': answered_calls,
        'average_call_duration': average_call_duration,
        'recent_calls': recent_calls,
        'hourly_calls': hourly_calls,
        'daily_trends': daily_trends,
        'daily_trend_label': daily_trend_label,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'time_period': time_period,
        'custom_date_range': custom_date_range,
        'date_range_label': date_range_label,
        'missed_call_rate': round((missed_calls / total_ivr_calls * 100) if total_ivr_calls > 0 else 0, 1),
        'answer_rate': round((answered_calls / total_ivr_calls * 100) if total_ivr_calls > 0 else 0, 1),
    }

    from django.urls import reverse
    context.update(_filter_toolbar_context(
        time_period, start_date, end_date, custom_date_range, date_range_label,
        toolbar_title='Call Center',
        filter_base_url=reverse('cdr3cx:call_center_dashboard'),
        reset_url=reverse('cdr3cx:call_center_dashboard'),
        show_nav_links=True,
    ))

    return render(request, 'cdr/callcenter/dashboard.html', context)


@login_required 
def agent_details(request, agent_extension):
    """
    Detailed view for a specific agent's call center performance
    """
    if not request.user.company:
        return render(request, 'cdr/callcenter/agent_details.html', {'error': 'No company assigned'})

    start_date, end_date, time_period, custom_date_range = _resolve_callcenter_date_range(request)
    date_range_label = _date_range_label(time_period, start_date, end_date, custom_date_range)

    # Get agent info
    agent_name = f"Extension {agent_extension}"
    try:
        agent_extension_obj = Extension.objects.get(
            extension=agent_extension,
            company=request.user.company
        )
        if agent_extension_obj.full_name:
            agent_name = agent_extension_obj.full_name
        elif agent_extension_obj.first_name or agent_extension_obj.last_name:
            agent_name = f"{agent_extension_obj.first_name or ''} {agent_extension_obj.last_name or ''}".strip()
    except Extension.DoesNotExist:
        pass

    # Agent's call center calls
    agent_calls = CallRecord.objects.filter(
        company=request.user.company,
        call_time__range=[start_date, end_date],
        final_dn=agent_extension
    ).filter(
        call_center_call_filter()
    )

    if agent_name == f"Extension {agent_extension}":
        disp = (
            CallRecord.objects.filter(
                company=request.user.company,
                final_dn=agent_extension,
            )
            .exclude(final_dispname__isnull=True)
            .exclude(final_dispname='')
            .values_list('final_dispname', flat=True)
            .first()
        )
        if disp:
            agent_name = disp

    # Statistics
    total_calls = agent_calls.count()
    answered_calls = agent_calls.filter(answered_call_filter()).count()
    total_duration = agent_calls.aggregate(Sum('duration'))['duration__sum'] or 0
    avg_duration = agent_calls.filter(answered_call_filter()).aggregate(Avg('duration'))['duration__avg'] or 0

    num_days = max((timezone.localtime(end_date).date() - timezone.localtime(start_date).date()).days + 1, 1)
    calls_per_day = round(total_calls / num_days, 1) if total_calls else 0
    answer_rate = round((answered_calls / total_calls * 100) if total_calls > 0 else 0, 1)

    # Format durations
    total_hours = total_duration // 3600
    total_minutes = (total_duration % 3600) // 60
    total_duration_formatted = f"{total_hours}h {total_minutes}m"

    avg_minutes = int(avg_duration // 60)
    avg_seconds = int(avg_duration % 60)
    avg_duration_formatted = f"{avg_minutes}:{avg_seconds:02d}"

    hourly_map = {
        row['hour']: row['calls']
        for row in agent_calls.annotate(hour=ExtractHour('call_time'))
        .values('hour').annotate(calls=Count('id'))
    }
    hourly_calls = [
        {'hour': f"{hour:02d}:00", 'calls': hourly_map.get(hour, 0)}
        for hour in range(24)
    ]
    daily_trends, daily_trend_label = _build_daily_trends(agent_calls, start_date, end_date)

    recent_calls = agent_calls.order_by('-call_time')[:50]

    # Real agent-side ACD performance from the 3CX XAPI (AgentQueueDailyStats) —
    # the genuine answered/lost/AHT/occupancy the socket CDR can't supply. Many
    # ACD agents have no Extension row, so this is often the substantive section.
    from acd.kpi import agent_acd_detail
    agent_acd = agent_acd_detail(request.user.company, agent_extension, start_date, end_date)
    if agent_acd.get('available'):
        agent_acd['aht_formatted'] = format_seconds(agent_acd['aht_seconds'])
        agent_acd['talk_formatted'] = format_seconds(agent_acd['talk_seconds'])
        agent_acd['logged_in_formatted'] = format_seconds(agent_acd['logged_in_seconds'])
        for q in agent_acd['per_queue']:
            q['aht_formatted'] = format_seconds(q['aht_seconds'])
        # Prefer the real ACD display name when no Extension/socket name resolved.
        if agent_name == f"Extension {agent_extension}":
            agent_name = agent_acd['name']

    survey_metrics = None
    if request.user.company.surveys_available:
        from surveys.services.metrics import agent_survey_metrics
        survey_metrics = agent_survey_metrics(
            request.user.company, agent_extension,
            timezone.localtime(start_date).date(),
            timezone.localtime(end_date).date(),
        )

    from django.urls import reverse
    agent_url = reverse('cdr3cx:agent_details', args=[agent_extension])
    dashboard_url = reverse('cdr3cx:call_center_dashboard')

    context = {
        'agent_extension': agent_extension,
        'agent_name': agent_name,
        'agent_acd': agent_acd,
        'total_calls': total_calls,
        'answered_calls': answered_calls,
        'answer_rate': answer_rate,
        'calls_per_day': calls_per_day,
        'total_duration_formatted': total_duration_formatted,
        'total_duration_seconds': total_duration,
        'avg_duration_formatted': avg_duration_formatted,
        'recent_calls': recent_calls,
        'hourly_calls': hourly_calls,
        'daily_trends': daily_trends,
        'daily_trend_label': daily_trend_label,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'time_period': time_period,
        'custom_date_range': custom_date_range,
        'date_range_label': date_range_label,
        'survey_metrics': survey_metrics,
        'surveys_available': request.user.company.surveys_available,
    }
    context.update(_filter_toolbar_context(
        time_period, start_date, end_date, custom_date_range, date_range_label,
        toolbar_title=agent_name,
        toolbar_subtitle=f"Ext. {agent_extension}",
        filter_base_url=agent_url,
        reset_url=agent_url,
        back_url=f"{dashboard_url}?start_date={start_date.strftime('%Y-%m-%d')}&end_date={end_date.strftime('%Y-%m-%d')}",
        show_nav_links=False,
    ))

    return render(request, 'cdr/callcenter/agent_details.html', context)


@login_required
def queue_details(request, queue_dn):
    """Deep-dive into one ACD queue: per-agent answered/lost productivity,
    abandoned-call detail (real seconds waited before hangup) and a daily call
    trend -- all from the 3CX XAPI queue stats. Reached by clicking a queue row
    on the call-center dashboard's "ACD Queues" table. Mirrors agent_details.
    """
    if not request.user.company:
        return render(request, 'cdr/callcenter/queue_details.html', {'error': 'No company assigned'})

    from django.db.models import Max
    from acd.models import Queue, QueueDailyStats, AgentQueueDailyStats, QueueAbandonedCall

    start_date, end_date, time_period, custom_date_range = _resolve_callcenter_date_range(request)
    date_range_label = _date_range_label(time_period, start_date, end_date, custom_date_range)
    sd = timezone.localtime(start_date).date()
    ed = timezone.localtime(end_date).date()

    queue = Queue.objects.filter(company=request.user.company, external_id=queue_dn).first()
    if not queue:
        return render(request, 'cdr/callcenter/queue_details.html', {
            'error': f'No queue found for extension {queue_dn}',
        })
    queue_name = queue.name

    # Queue totals over the window (real wait timing from the XAPI feed).
    qstats = QueueDailyStats.objects.filter(queue=queue, stat_date__range=[sd, ed])
    agg = qstats.aggregate(
        calls=Sum('calls'), answered=Sum('answered'),
        ring=Sum('ring_time_seconds'), talk=Sum('talk_time_seconds'),
    )
    calls = agg['calls'] or 0
    answered = agg['answered'] or 0
    abandoned = max(0, calls - answered)
    answer_rate = round(answered / calls * 100, 1) if calls else 0
    abandon_rate = round(abandoned / calls * 100, 1) if calls else 0
    asa_seconds = round(agg['ring'] / calls, 1) if agg['ring'] and calls else None
    avg_talk_seconds = round(agg['talk'] / answered, 1) if agg['talk'] and answered else None

    # Real abandoned-call detail (true seconds the caller waited before giving up).
    ab_qs = QueueAbandonedCall.objects.filter(queue=queue, call_time__date__range=[sd, ed])
    ab_agg = ab_qs.aggregate(n=Count('id'), avg_wait=Avg('wait_seconds'), max_wait=Max('wait_seconds'))
    abandoned_calls = list(ab_qs.order_by('-call_time')[:100])

    # Per-agent productivity within this queue.
    agents = []
    for r in (AgentQueueDailyStats.objects.filter(queue=queue, stat_date__range=[sd, ed])
              .values('agent_dn', 'agent_name')
              .annotate(answered=Sum('answered'), lost=Sum('lost'),
                        talk=Sum('talk_time_seconds'), logged_in=Sum('logged_in_seconds'))
              .order_by('-answered')):
        a = r['answered'] or 0
        lost = r['lost'] or 0
        rings = a + lost
        talk = r['talk'] or 0
        li = r['logged_in'] or 0
        agents.append({
            'dn': r['agent_dn'],
            'name': r['agent_name'] or f"Ext {r['agent_dn']}",
            'answered': a,
            'lost': lost,
            'answer_rate': round(a / rings * 100, 1) if rings else None,
            'talk_formatted': format_seconds(talk),
            'aht_formatted': format_seconds(round(talk / a, 1)) if a else '\u2014',
            'occupancy_pct': round(talk / li * 100, 1) if li else None,
        })

    # Daily trend (calls / answered / abandoned) for the chart.
    daily_map = {row['stat_date']: row
                 for row in qstats.values('stat_date').annotate(c=Sum('calls'), a=Sum('answered'))}
    daily_trends = []
    day = sd
    while day <= ed:
        row = daily_map.get(day, {})
        c = row.get('c', 0) or 0
        a = row.get('a', 0) or 0
        daily_trends.append({
            'date': day.strftime('%Y-%m-%d'),
            'label': day.strftime('%m-%d'),
            'total_calls': c,
            'answered': a,
            'abandoned': max(0, c - a),
        })
        day += timedelta(days=1)

    has_data = bool(qstats.exists() or abandoned_calls or agents)

    survey_metrics = None
    if request.user.company.surveys_available:
        from surveys.services.metrics import queue_survey_metrics
        survey_metrics = queue_survey_metrics(
            request.user.company, queue_dn, sd, ed,
        )

    context = {
        'queue': queue,
        'queue_dn': queue_dn,
        'queue_name': queue_name,
        'has_data': has_data,
        'calls': calls,
        'answered': answered,
        'abandoned': abandoned,
        'answer_rate': answer_rate,
        'abandon_rate': abandon_rate,
        'asa_formatted': format_seconds(asa_seconds),
        'avg_talk_formatted': format_seconds(avg_talk_seconds),
        'abandon_count': ab_agg['n'] or 0,
        'avg_abandon_wait_formatted': format_seconds(ab_agg['avg_wait']),
        'max_abandon_wait_formatted': format_seconds(ab_agg['max_wait']),
        'agents': agents,
        'abandoned_calls': abandoned_calls,
        'daily_trends': daily_trends,
        'daily_trend_label': date_range_label,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'time_period': time_period,
        'custom_date_range': custom_date_range,
        'date_range_label': date_range_label,
        'survey_metrics': survey_metrics,
        'surveys_available': request.user.company.surveys_available,
    }

    from django.urls import reverse
    queue_url = reverse('cdr3cx:queue_details', args=[queue_dn])
    dashboard_url = reverse('cdr3cx:call_center_dashboard')
    context.update(_filter_toolbar_context(
        time_period, start_date, end_date, custom_date_range, date_range_label,
        toolbar_title=queue_name,
        toolbar_subtitle=f"Queue {queue_dn}",
        filter_base_url=queue_url,
        reset_url=queue_url,
        back_url=f"{dashboard_url}?start_date={start_date.strftime('%Y-%m-%d')}&end_date={end_date.strftime('%Y-%m-%d')}",
        show_nav_links=False,
    ))

    return render(request, 'cdr/callcenter/queue_details.html', context)


@login_required
def missed_calls_details(request):
    """
    Detailed view of missed call center calls
    """
    if not request.user.company:
        return render(request, 'cdr/callcenter/missed_calls.html', {'error': 'No company assigned'})

    start_date, end_date, time_period, custom_date_range = _resolve_callcenter_date_range(request, default_period='7d')
    date_range_label = _date_range_label(time_period, start_date, end_date, custom_date_range)

    # Missed call center calls
    missed_calls = CallRecord.objects.filter(
        company=request.user.company,
        call_time__range=[start_date, end_date]
    ).filter(
        call_center_call_filter()
    ).filter(
        missed_call_filter()
    ).order_by('-call_time')

    # Pagination could be added here if needed
    
    context = {
        'missed_calls': missed_calls,
        'total_missed': missed_calls.count(),
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'time_period': time_period,
        'custom_date_range': custom_date_range,
        'date_range_label': date_range_label,
    }

    from django.urls import reverse
    context.update(_filter_toolbar_context(
        time_period, start_date, end_date, custom_date_range, date_range_label,
        toolbar_title='Missed Calls',
        filter_base_url=reverse('cdr3cx:missed_calls_details'),
        reset_url=reverse('cdr3cx:missed_calls_details'),
        show_nav_links=False,
    ))

    return render(request, 'cdr/callcenter/missed_calls.html', context)


def format_time_difference(minutes):
    """
    Format time difference in minutes to readable format like "1D 4H 30M"
    """
    if minutes < 0:
        return "0M"

    days = int(minutes // (24 * 60))
    remaining = minutes % (24 * 60)
    hours = int(remaining // 60)
    mins = int(remaining % 60)

    parts = []
    if days > 0:
        parts.append(f"{days}D")
    if hours > 0:
        parts.append(f"{hours}H")
    if mins > 0 or len(parts) == 0:
        parts.append(f"{mins}M")

    return " ".join(parts)


@login_required
def call_back_tracking(request):
    """
    Call Back Tracking Dashboard showing:
    - Missed calls and their callback attempts
    - Callback success rates
    - Agent callback performance
    """

    if not request.user.company:
        return render(request, 'cdr/callcenter/call_back_tracking.html', {'error': 'No company assigned'})

    start_date, end_date, time_period, custom_date_range = _resolve_callcenter_date_range(request, default_period='7d')
    date_range_label = _date_range_label(time_period, start_date, end_date, custom_date_range)

    # Get selected agent filter
    selected_agent = request.GET.get('agent')

    # 1. Find all missed IVR calls in the date range
    missed_calls = CallRecord.objects.filter(
        company=request.user.company,
        call_time__range=[start_date, end_date]
    ).filter(
        call_center_call_filter()
    ).filter(
        missed_call_filter()
    ).values('from_no').distinct()

    # Extract the phone numbers
    missed_numbers = [call['from_no'] for call in missed_calls]

    # 2. Find callback attempts (outgoing calls from extensions to missed numbers)
    callback_attempts_query = CallRecord.objects.filter(
        company=request.user.company,
        call_time__range=[start_date, end_date],
        from_type__iexact='extension',  # Outgoing from extension
        callee__in=missed_numbers  # To numbers that missed IVR calls
    )

    # Apply agent filter if selected
    if selected_agent:
        callback_attempts_query = callback_attempts_query.filter(caller=selected_agent)

    callback_attempts = callback_attempts_query.order_by('-call_time')

    # 3. Build callback tracking data
    callback_tracking = []

    # If agent is selected, get the numbers this agent called
    if selected_agent:
        agent_called_numbers = list(callback_attempts.values_list('callee', flat=True).distinct())
        # Filter missed_numbers to only those the agent called, and remove duplicates
        relevant_missed_numbers = list(set([num for num in missed_numbers if num in agent_called_numbers]))
    else:
        relevant_missed_numbers = missed_numbers[:50]  # Limit to 50 for performance when no agent filter

    for number in relevant_missed_numbers[:100]:  # Allow more when filtering by agent
        # Get the original missed call info (most recent missed call for this number)
        original_missed = CallRecord.objects.filter(
            company=request.user.company,
            call_time__range=[start_date, end_date],
            from_no=number
        ).filter(
            call_center_call_filter()
        ).filter(
            missed_call_filter()
        ).order_by('-call_time').first()

        if not original_missed:
            continue

        # Find all callback attempts to this number AFTER the missed call
        # We want callbacks that happen AFTER the customer missed the IVR call
        callbacks_query = CallRecord.objects.filter(
            company=request.user.company,
            call_time__range=[start_date, end_date],
            from_type='Extension',
            callee=number,
            call_time__gt=original_missed.call_time  # MUST be after the missed call
        )

        # Apply agent filter if selected
        if selected_agent:
            callbacks_query = callbacks_query.filter(caller=selected_agent)

        callbacks = callbacks_query.order_by('call_time')

        callback_success = callbacks.filter(time_answered__isnull=False).exists()
        total_attempts = callbacks.count()

        if total_attempts > 0:  # Only include numbers that had callback attempts AFTER they missed
            # Get agent info for the latest callback
            latest_callback = callbacks.last()
            agent_name = "Unknown Agent"
            if latest_callback and latest_callback.caller:
                try:
                    from accounts.models import Extension
                    agent_ext = Extension.objects.get(
                        extension=latest_callback.caller,
                        company=request.user.company
                    )
                    agent_name = agent_ext.user.get_full_name() if agent_ext.user else f"Ext. {latest_callback.caller}"
                except Extension.DoesNotExist:
                    agent_name = f"Ext. {latest_callback.caller}"

            # Calculate time to callback (first callback after missed call)
            first_callback_after = callbacks.first()
            time_to_callback = (first_callback_after.call_time - original_missed.call_time).total_seconds() / 60

            # Enhance each callback with calculated time difference
            callbacks_with_time = []
            for cb in callbacks:
                minutes_diff = (cb.call_time - original_missed.call_time).total_seconds() / 60
                cb_dict = {
                    'id': cb.id,
                    'call_time': cb.call_time,
                    'time_answered': cb.time_answered,
                    'duration': cb.duration,
                    'reason_terminated': cb.reason_terminated,
                    'caller': cb.caller,
                    'callee': cb.callee,
                    'from_no': cb.from_no,
                    'to_no': cb.to_no,
                    # Calculate minutes after missed call
                    'minutes_after_missed': round(minutes_diff, 1),
                    'formatted_time_diff': format_time_difference(minutes_diff)
                }
                callbacks_with_time.append(cb_dict)

            callback_tracking.append({
                'missed_number': number,
                'missed_time': original_missed.call_time,
                'missed_ivr': original_missed.to_dn,
                'total_attempts': total_attempts,
                'successful_callback': callback_success,
                'latest_callback_time': latest_callback.call_time if latest_callback else None,
                'agent_name': agent_name,
                'agent_extension': latest_callback.caller if latest_callback else None,
                'callbacks': callbacks_with_time,
                'time_to_callback': time_to_callback,
                'formatted_response_time': format_time_difference(time_to_callback)
            })

    # Sort by latest callback time
    callback_tracking.sort(key=lambda x: x['latest_callback_time'] or timezone.now(), reverse=True)

    # 4. Summary statistics
    total_missed_with_callbacks = len(callback_tracking)
    successful_callbacks = len([ct for ct in callback_tracking if ct['successful_callback']])
    callback_success_rate = round((successful_callbacks / total_missed_with_callbacks * 100) if total_missed_with_callbacks > 0 else 0, 1)

    # 5. Agent callback performance
    agent_performance = {}
    for attempt in callback_attempts:
        agent_ext = attempt.caller
        if agent_ext not in agent_performance:
            agent_performance[agent_ext] = {
                'extension': agent_ext,
                'total_attempts': 0,
                'successful_attempts': 0,
                'total_talk_time': 0
            }

        agent_performance[agent_ext]['total_attempts'] += 1
        if attempt.time_answered:
            agent_performance[agent_ext]['successful_attempts'] += 1
            agent_performance[agent_ext]['total_talk_time'] += attempt.duration or 0

    # Convert to list and calculate success rates
    agent_performance_list = []
    for agent_data in agent_performance.values():
        success_rate = round((agent_data['successful_attempts'] / agent_data['total_attempts'] * 100) if agent_data['total_attempts'] > 0 else 0, 1)

        # Get agent name
        agent_name = f"Ext. {agent_data['extension']}"
        try:
            from accounts.models import Extension
            agent_ext = Extension.objects.get(
                extension=agent_data['extension'],
                company=request.user.company
            )
            agent_name = agent_ext.user.get_full_name() if agent_ext.user else f"Ext. {agent_data['extension']}"
        except Extension.DoesNotExist:
            pass

        agent_performance_list.append({
            'extension': agent_data['extension'],
            'name': agent_name,
            'total_attempts': agent_data['total_attempts'],
            'successful_attempts': agent_data['successful_attempts'],
            'success_rate': success_rate,
            'total_talk_time': agent_data['total_talk_time']
        })

    # Sort by total attempts
    agent_performance_list.sort(key=lambda x: x['total_attempts'], reverse=True)

    context = {
        'callback_tracking': callback_tracking,
        'agent_performance': agent_performance_list,
        'total_missed_with_callbacks': total_missed_with_callbacks,
        'successful_callbacks': successful_callbacks,
        'callback_success_rate': callback_success_rate,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'time_period': time_period,
        'custom_date_range': custom_date_range,
        'date_range_label': date_range_label,
        'selected_agent': selected_agent,
    }

    from django.urls import reverse
    context.update(_filter_toolbar_context(
        time_period, start_date, end_date, custom_date_range, date_range_label,
        toolbar_title='Call Back Tracking',
        filter_base_url=reverse('cdr3cx:call_back_tracking'),
        reset_url=reverse('cdr3cx:call_back_tracking'),
        show_nav_links=False,
    ))


# ---------------------------------------------------------------------------
# P2.4 — Live supervisor wallboard (real-time, driven by the 3CX ActiveCalls feed)
# ---------------------------------------------------------------------------
@login_required
def callcenter_wallboard(request):
    """Full-screen auto-refreshing wallboard. Data is fetched client-side from
    wallboard_data so the page itself is light and the PBX is polled at most once
    per refresh window (the snapshot is Redis-cached)."""
    return render(request, 'cdr/callcenter/wallboard.html', {
        'company_name': getattr(request.user.company, 'name', ''),
    })


@login_required
def wallboard_data(request):
    """JSON snapshot for the wallboard poller."""
    from django.http import JsonResponse
    from acd.live import wallboard_snapshot

    company = request.user.company
    if not company:
        return JsonResponse({'ok': False, 'error': 'No company assigned'}, status=400)
    return JsonResponse(wallboard_snapshot(company))


# ---------------------------------------------------------------------------
# P3.2 — Per-call cradle-to-grave drill-down
# ---------------------------------------------------------------------------
@login_required
def call_detail(request, pk):
    """Full detail / timeline for one call, plus related calls from the same
    caller nearby. The 3CX socket CDR is one row per call (correlation_id is not
    populated), so true multi-leg segmentation needs the DB-pull feed — surfaced
    here as a note rather than faked."""
    from django.shortcuts import get_object_or_404
    call = get_object_or_404(CallRecord, pk=pk, company=request.user.company)

    legs = call.legs.all() if hasattr(call, 'legs') else []
    caller_key = (call.from_no or call.caller or '').strip()
    related = []
    if caller_key:
        win_lo = call.call_time - timedelta(hours=2)
        win_hi = call.call_time + timedelta(hours=2)
        related = (CallRecord.objects.filter(
            company=request.user.company, call_time__range=[win_lo, win_hi])
            .filter(Q(from_no=caller_key) | Q(caller=caller_key))
            .exclude(pk=call.pk).order_by('call_time')[:20])

    # Timeline waypoints (only those present).
    timeline = []
    if call.call_time:
        timeline.append(('Call started', call.call_time))
    if call.time_answered:
        timeline.append(('Answered', call.time_answered))
    if call.time_end:
        timeline.append(('Ended', call.time_end))

    return render(request, 'cdr/callcenter/call_detail.html', {
        'call': call, 'legs': legs, 'related': related, 'timeline': timeline,
        'has_correlation': bool((call.correlation_id or '').strip()),
    })