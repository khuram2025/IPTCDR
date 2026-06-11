"""Celery tasks for survey linking and rollups."""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name='surveys.tasks.link_unmatched_survey_responses')
def link_unmatched_survey_responses(limit=200):
    """Retry linking survey responses whose CallRecord arrived after the survey."""
    from surveys.models import SurveyResponse
    from surveys.services.linking import link_call_record

    qs = (
        SurveyResponse.objects.filter(match_confidence='unmatched')
        .select_related('campaign', 'company')
        .order_by('-completed_at')[:limit]
    )
    linked = 0
    for resp in qs:
        call_record, agent, queue, match = link_call_record(
            resp.company,
            resp.caller,
            resp.completed_at,
            agent_dn=resp.agent_dn_hint,
            queue_dn=resp.queue_dn_hint,
            window_minutes=resp.campaign.match_window_minutes,
        )
        if match == 'unmatched':
            continue
        resp.call_record = call_record
        resp.agent = agent or resp.agent
        resp.queue = queue or resp.queue
        resp.match_confidence = match
        resp.save(update_fields=['call_record', 'agent', 'queue', 'match_confidence'])
        linked += 1
    return {'linked': linked, 'checked': qs.count()}


@shared_task(name='surveys.tasks.compute_survey_daily_rollups')
def compute_survey_daily_rollups(company_id=None, days_back=35):
    from surveys.services.metrics import rebuild_daily_rollups
    upserts = rebuild_daily_rollups(company_id=company_id, days_back=days_back)
    return {'upserts': upserts, 'at': timezone.now().isoformat()}


@shared_task(name='surveys.tasks.post_survey_ingest')
def post_survey_ingest(response_id: int):
    """Async follow-up after ingest: rollups + webhook."""
    from surveys.models import SurveyResponse
    from api.services.webhooks import emit

    try:
        resp = SurveyResponse.objects.select_related(
            'company', 'campaign', 'agent', 'queue', 'call_record',
        ).prefetch_related('answers').get(pk=response_id)
    except SurveyResponse.DoesNotExist:
        return {'error': 'not_found'}

    compute_survey_daily_rollups.delay(company_id=resp.company_id, days_back=7)

    rating = resp.answers.filter(tag__in=('rating', 'csat')).first()
    solved = resp.answers.filter(tag='solved').first()
    payload = {
        'event': 'survey.completed',
        'company_id': resp.company_id,
        'response_id': resp.pk,
        'campaign_slug': resp.campaign.slug,
        'caller': resp.caller,
        'completed_at': resp.completed_at.isoformat(),
        'match_confidence': resp.match_confidence,
        'call_record_id': resp.call_record_id,
        'agent_id': resp.agent_id,
        'queue_id': resp.queue_id,
        'rating': rating.value_numeric if rating else None,
        'solved': solved.value_bool if solved and solved.value_bool is not None else (
            (solved.value_text or '').upper() == 'YES' if solved else None
        ),
    }
    count = emit(resp.company, 'survey.completed', payload)
    return {'webhooks': count}
