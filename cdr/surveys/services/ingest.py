"""CFD survey ingest pipeline."""
import hashlib
import logging
from datetime import datetime

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from surveys.models import SurveyAnswer, SurveyCampaign, SurveyQuestion, SurveyResponse
from surveys.services.linking import link_call_record

logger = logging.getLogger(__name__)


class IngestError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def _parse_completed_at(value):
    if not value:
        return timezone.now()
    if isinstance(value, datetime):
        dt = value
    else:
        dt = parse_datetime(str(value))
    if dt is None:
        return timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _idempotency_key(campaign_id, caller, completed_at):
    raw = f'{campaign_id}:{caller}:{completed_at.isoformat()}'
    return hashlib.sha256(raw.encode()).hexdigest()


def _parse_yes_no(value: str):
    v = (value or '').strip().upper()
    if v in ('YES', 'Y', '1', 'TRUE'):
        return True, v
    if v in ('NO', 'N', '2', 'FALSE'):
        return False, v
    return None, v


def _coerce_answer(question, raw_value: str):
    text = (raw_value or '').strip()
    numeric = None
    boolean = None
    recording = ''

    if question and question.question_type == SurveyQuestion.TYPE_YES_NO:
        boolean, text = _parse_yes_no(text)
    elif question and question.question_type == SurveyQuestion.TYPE_RECORDING:
        recording = text
    else:
        try:
            numeric = float(text)
        except (TypeError, ValueError):
            numeric = None

    return {
        'value_text': text,
        'value_numeric': numeric,
        'value_bool': boolean,
        'recording_path': recording,
    }


@transaction.atomic
def ingest_survey_response(campaign: SurveyCampaign, payload: dict) -> tuple[SurveyResponse, bool]:
    """Persist a survey response. Returns (response, created)."""
    if not campaign.is_active:
        raise IngestError('Campaign is inactive', 403)
    if not campaign.license_verified:
        raise IngestError('CFD license not verified for this campaign', 403)
    if not campaign.company.survey_enabled or not campaign.company.survey_cfd_verified:
        raise IngestError('Surveys not enabled for this tenant', 403)

    caller = (payload.get('caller') or '').strip()
    if not caller:
        raise IngestError('caller is required')

    completed_at = _parse_completed_at(payload.get('completed_at'))
    idem = _idempotency_key(campaign.pk, caller, completed_at)

    existing = SurveyResponse.objects.filter(idempotency_key=idem).first()
    if existing:
        return existing, False

    call_record_id = payload.get('call_record_id')
    correlation_id = payload.get('correlation_id')
    agent_dn = (payload.get('agent_dn') or '').strip()
    queue_dn = (payload.get('queue_dn') or '').strip()

    call_record, agent, queue, match = link_call_record(
        campaign.company, caller, completed_at,
        call_record_id=call_record_id,
        correlation_id=correlation_id,
        agent_dn=agent_dn,
        queue_dn=queue_dn,
        window_minutes=campaign.match_window_minutes,
    )

    recording_path = ''
    answers_data = payload.get('answers') or []
    for item in answers_data:
        if (item.get('tag') or '').lower() == 'comments' and item.get('value'):
            recording_path = str(item['value'])

    response = SurveyResponse.objects.create(
        company=campaign.company,
        campaign=campaign,
        caller=caller,
        completed_at=completed_at,
        call_record=call_record,
        agent=agent or (call_record.agent if call_record else None),
        queue=queue or (call_record.queue if call_record else None),
        match_confidence=match,
        idempotency_key=idem,
        raw_payload=payload,
        recording_path=recording_path,
        agent_dn_hint=agent_dn,
        queue_dn_hint=queue_dn,
    )

    questions_by_tag = {q.tag: q for q in campaign.questions.all()}
    for item in answers_data:
        tag = (item.get('tag') or '').strip()
        if not tag:
            continue
        question = questions_by_tag.get(tag)
        coerced = _coerce_answer(question, str(item.get('value', '')))
        SurveyAnswer.objects.create(
            response=response,
            question=question,
            tag=tag,
            **coerced,
        )

    return response, True


def resolve_campaign_from_token(token: str) -> SurveyCampaign:
    if not token:
        raise IngestError('Missing X-Survey-Token header', 401)
    try:
        return SurveyCampaign.objects.select_related('company').get(
            ingest_token=token, is_active=True,
        )
    except SurveyCampaign.DoesNotExist:
        raise IngestError('Invalid survey token', 401)


def resolve_campaign_by_slug(company, slug: str) -> SurveyCampaign:
    try:
        return SurveyCampaign.objects.get(company=company, slug=slug, is_active=True)
    except SurveyCampaign.DoesNotExist:
        raise IngestError(f'Unknown campaign slug: {slug}', 404)
