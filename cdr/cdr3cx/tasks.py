"""Celery tasks for async enrichment, pattern re-apply, and scheduled jobs."""
import logging
from decimal import Decimal

from celery import shared_task
from django.db import transaction

logger = logging.getLogger(__name__)


@shared_task
def heartbeat():
    """No-op task to verify worker + beat are running."""
    logger.info('celery heartbeat ok')
    return 'ok'


@shared_task
def enforce_quota_state(extension_id):
    """P4.3 — block/unblock an extension's external calling on the PBX to match its
    quota balance. Acts only on transitions (idempotent) and only actually calls the
    PBX when settings.QUOTA_ENFORCEMENT_ENABLED is True — otherwise it records the
    decision so the behaviour can be validated before going live."""
    from django.conf import settings
    from cdr3cx.models import UserQuota
    from cdr3cx.blockExternalCall import set_external_call

    try:
        uq = UserQuota.objects.select_related('extension', 'extension__company').get(
            extension_id=extension_id)
    except UserQuota.DoesNotExist:
        return {'extension': extension_id, 'error': 'no quota'}

    should_block = uq.should_block()
    if should_block == uq.is_blocked:
        return {'extension': extension_id, 'changed': False, 'blocked': uq.is_blocked}

    enabled = getattr(settings, 'QUOTA_ENFORCEMENT_ENABLED', False)
    applied = None
    if enabled:
        company = uq.extension.company
        applied = set_external_call(
            uq.extension.extension, allow_external=not should_block,
            base_url=getattr(company, 'pbx_api_url', None) or None,
            user=getattr(company, 'pbx_api_user', None) or None,
            password=getattr(company, 'pbx_api_password', None) or None,
        )
        if not applied:
            logger.warning('enforce_quota_state: PBX update failed for ext %s',
                           uq.extension.extension)
            return {'extension': extension_id, 'changed': False, 'applied': False,
                    'would_block': should_block}
    else:
        logger.info('enforce_quota_state (disabled): would %s ext %s',
                    'BLOCK' if should_block else 'UNBLOCK', uq.extension.extension)

    uq.is_blocked = should_block
    uq.save(update_fields=['is_blocked'])
    return {'extension': extension_id, 'changed': True, 'blocked': should_block,
            'enforced_on_pbx': bool(enabled and applied)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def reapply_call_pattern(self, pattern_id, last_id=0, batch_size=500):
    """Re-apply a CallPattern to matching records in bounded batches."""
    from cdr3cx.models import CallPattern, CallRecord

    try:
        pattern = CallPattern.objects.select_related('company').get(pk=pattern_id)
    except CallPattern.DoesNotExist:
        logger.warning('CallPattern %s no longer exists', pattern_id)
        return 0

    prefix = pattern.pattern.replace('x', '')
    qs = (
        CallRecord.objects.filter(
            company=pattern.company,
            callee__startswith=prefix,
            to_type__iexact='line',
            id__gt=last_id,
        )
        .order_by('id')[:batch_size]
    )

    updated = 0
    max_id = last_id
    for record in qs:
        duration_minutes = (record.duration + 59) // 60 if record.duration else 0
        record.call_category = pattern.call_type
        record.call_rate = pattern.rate_per_min
        record.total_cost = Decimal(duration_minutes) * pattern.rate_per_min
        record.save(update_fields=['call_category', 'call_rate', 'total_cost'])
        updated += 1
        max_id = record.id

    if updated == batch_size:
        reapply_call_pattern.delay(pattern_id, max_id, batch_size)

    logger.info(
        'reapply_call_pattern pattern=%s updated=%s last_id=%s',
        pattern_id, updated, max_id,
    )
    return updated
