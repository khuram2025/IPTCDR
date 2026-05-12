"""Wire model signals to webhook fan-out.

Lazy-imports avoid app-loading order issues at startup.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='cdr3cx.CallRecord')
def _emit_call_completed(sender, instance, created, **kwargs):
    if not created or instance.company_id is None:
        return
    from .services.webhooks import emit
    payload = {
        'id':            instance.pk,
        'source_pbx':    instance.source_pbx,
        'caller':        instance.caller,
        'callee':        instance.callee,
        'call_time':     instance.call_time.isoformat() if instance.call_time else None,
        'duration':      instance.duration,
        'total_cost':    str(instance.total_cost) if instance.total_cost is not None else None,
        'call_category': instance.call_category,
    }
    emit(instance.company, 'call.completed', payload)


@receiver(post_save, sender='billing.FraudIncident')
def _emit_fraud_detected(sender, instance, created, **kwargs):
    if not created:
        return
    from .services.webhooks import emit
    payload = {
        'id':           instance.pk,
        'severity':     instance.severity,
        'summary':      instance.summary,
        'detail':       instance.detail,
        'detected_at':  instance.detected_at.isoformat(),
        'rule_id':      instance.rule_id,
        'call_id':      instance.triggering_call_id,
    }
    emit(instance.company, 'fraud.detected', payload)
