"""Survey KPI aggregation."""
from datetime import date, timedelta

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from surveys.models import SurveyAnswer, SurveyDailyRollup, SurveyQuestion, SurveyResponse


def _rating_answers_qs(company, start, end, **filters):
    return SurveyAnswer.objects.filter(
        response__company=company,
        response__completed_at__date__gte=start,
        response__completed_at__date__lte=end,
        tag__in=['rating', 'csat'],
        value_numeric__isnull=False,
        **filters,
    )


def compute_csat(company, start: date, end: date, **filters) -> dict:
    """CSAT = top-box (rating >= 4 on 5-point scale) / total ratings * 100."""
    qs = _rating_answers_qs(company, start, end, **filters)
    total = qs.count()
    if not total:
        return {'csat_pct': None, 'rating_count': 0, 'avg_rating': None}
    topbox = qs.filter(value_numeric__gte=4).count()
    avg = qs.aggregate(avg=Avg('value_numeric'))['avg']
    return {
        'csat_pct': round(topbox / total * 100, 1),
        'rating_count': total,
        'avg_rating': round(avg, 2) if avg is not None else None,
    }


def compute_solved_rate(company, start: date, end: date, **filters) -> dict:
    qs = SurveyAnswer.objects.filter(
        response__company=company,
        response__completed_at__date__gte=start,
        response__completed_at__date__lte=end,
        tag='solved',
        **filters,
    )
    total = qs.count()
    if not total:
        return {'solved_pct': None, 'solved_count': 0}
    yes = qs.filter(Q(value_bool=True) | Q(value_text__iexact='YES')).count()
    return {'solved_pct': round(yes / total * 100, 1), 'solved_count': yes, 'solved_total': total}


def compute_nps(company, start: date, end: date, **filters) -> dict:
    qs = SurveyAnswer.objects.filter(
        response__company=company,
        response__completed_at__date__gte=start,
        response__completed_at__date__lte=end,
        tag='nps',
        value_numeric__isnull=False,
        **filters,
    )
    total = qs.count()
    if not total:
        return {'nps_score': None, 'nps_total': 0}
    promoters = qs.filter(value_numeric__gte=9).count()
    detractors = qs.filter(value_numeric__lte=6).count()
    return {
        'nps_score': round((promoters - detractors) / total * 100, 1),
        'nps_total': total,
        'nps_promoters': promoters,
        'nps_detractors': detractors,
    }


def survey_dashboard_metrics(company, start: date, end: date) -> dict:
    responses = SurveyResponse.objects.filter(
        company=company,
        completed_at__date__gte=start,
        completed_at__date__lte=end,
    )
    total = responses.count()
    matched = responses.exclude(match_confidence='unmatched').count()
    csat = compute_csat(company, start, end)
    solved = compute_solved_rate(company, start, end)
    nps = compute_nps(company, start, end)

    daily = list(
        responses.annotate(day=TruncDate('completed_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    rating_trend = list(
        _rating_answers_qs(company, start, end)
        .annotate(day=TruncDate('response__completed_at'))
        .values('day')
        .annotate(avg_rating=Avg('value_numeric'), count=Count('id'))
        .order_by('day')
    )

    by_queue = []
    for row in (
        responses.filter(queue__isnull=False)
        .values('queue_id', 'queue__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    ):
        q_csat = compute_csat(company, start, end, response__queue_id=row['queue_id'])
        by_queue.append({
            'queue_id': row['queue_id'],
            'queue_name': row['queue__name'],
            'count': row['count'],
            'csat_pct': q_csat['csat_pct'],
        })

    by_agent = []
    for row in (
        responses.filter(agent__isnull=False)
        .values('agent_id', 'agent__display_name', 'agent__external_id')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    ):
        a_csat = compute_csat(company, start, end, response__agent_id=row['agent_id'])
        by_agent.append({
            'agent_id': row['agent_id'],
            'agent_name': row['agent__display_name'] or row['agent__external_id'],
            'count': row['count'],
            'csat_pct': a_csat['csat_pct'],
        })

    campaign = company.survey_campaigns.filter(is_active=True).first()
    target = campaign.csat_target_pct if campaign else 80

    return {
        'total_responses': total,
        'matched_responses': matched,
        'match_rate': round(matched / total * 100, 1) if total else None,
        'csat': csat,
        'solved': solved,
        'nps': nps,
        'csat_target_pct': target,
        'daily_counts': daily,
        'rating_trend': rating_trend,
        'by_queue': by_queue,
        'by_agent': by_agent,
    }


def agent_survey_metrics(company, agent_external_id: str, start: date, end: date) -> dict:
    filters = {'response__agent__external_id': agent_external_id}
    csat = compute_csat(company, start, end, **filters)
    solved = compute_solved_rate(company, start, end, **filters)
    count = SurveyResponse.objects.filter(
        company=company,
        completed_at__date__gte=start,
        completed_at__date__lte=end,
        agent__external_id=agent_external_id,
    ).count()
    return {'response_count': count, **csat, **solved}


def queue_survey_metrics(company, queue_external_id: str, start: date, end: date) -> dict:
    filters = {'response__queue__external_id': queue_external_id}
    csat = compute_csat(company, start, end, **filters)
    solved = compute_solved_rate(company, start, end, **filters)
    count = SurveyResponse.objects.filter(
        company=company,
        completed_at__date__gte=start,
        completed_at__date__lte=end,
        queue__external_id=queue_external_id,
    ).count()
    return {'response_count': count, **csat, **solved}


def rebuild_daily_rollups(company_id=None, days_back=35) -> int:
    """Rebuild SurveyDailyRollup rows for the recent window."""
    today = timezone.localdate()
    start = today - timedelta(days=days_back)
    companies = []
    if company_id:
        from accounts.models import Company
        companies = list(Company.objects.filter(pk=company_id))
    else:
        from accounts.models import Company
        companies = list(Company.objects.filter(survey_enabled=True))

    upserts = 0
    for company in companies:
        responses = SurveyResponse.objects.filter(
            company=company,
            completed_at__date__gte=start,
            completed_at__date__lte=today,
        ).select_related('campaign', 'queue', 'agent').prefetch_related('answers')

        buckets = {}
        for resp in responses:
            d = timezone.localtime(resp.completed_at).date()
            key = (d, resp.campaign_id, resp.queue_id, resp.agent_id)
            buckets.setdefault(key, []).append(resp)

        for (d, camp_id, queue_id, agent_id), resps in buckets.items():
            rating_sum = rating_count = csat_top = 0
            solved_yes = solved_total = 0
            nps_p = nps_d = nps_t = 0
            for resp in resps:
                for ans in resp.answers.all():
                    if ans.tag in ('rating', 'csat') and ans.value_numeric is not None:
                        rating_count += 1
                        rating_sum += ans.value_numeric
                        if ans.value_numeric >= 4:
                            csat_top += 1
                    if ans.tag == 'solved':
                        solved_total += 1
                        if ans.value_bool or (ans.value_text or '').upper() == 'YES':
                            solved_yes += 1
                    if ans.tag == 'nps' and ans.value_numeric is not None:
                        nps_t += 1
                        if ans.value_numeric >= 9:
                            nps_p += 1
                        elif ans.value_numeric <= 6:
                            nps_d += 1

            obj, _ = SurveyDailyRollup.objects.update_or_create(
                company=company,
                stat_date=d,
                campaign_id=camp_id,
                queue_id=queue_id,
                agent_id=agent_id,
                defaults={
                    'response_count': len(resps),
                    'rating_count': rating_count,
                    'rating_sum': rating_sum,
                    'csat_topbox_count': csat_top,
                    'solved_yes_count': solved_yes,
                    'solved_total_count': solved_total,
                    'nps_promoters': nps_p,
                    'nps_detractors': nps_d,
                    'nps_total': nps_t,
                },
            )
            upserts += 1
    return upserts
