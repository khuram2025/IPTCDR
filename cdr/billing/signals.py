"""Connect CDR ingestion to the fraud evaluator.

Runs synchronously on ``post_save`` for now. To move to Celery (Phase 1 W1),
swap the inner call for ``evaluate_call.delay(instance.pk)``.
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .services.fraud import evaluate_call

logger = logging.getLogger(__name__)


@receiver(post_save, sender='cdr3cx.CallRecord')
def _evaluate_fraud_on_call_save(sender, instance, created, **kwargs):
    if not created or instance.company_id is None:
        return
    try:
        incidents = evaluate_call(instance)
        if incidents:
            logger.info("[fraud] %d incident(s) opened for call %s",
                        len(incidents), instance.pk)
    except Exception:  # pragma: no cover - defensive; never break call ingestion
        logger.exception("Fraud evaluation failed for call %s", instance.pk)
