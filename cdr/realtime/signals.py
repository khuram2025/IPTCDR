"""Connect domain events to the wallboard channel layer.

Every new ``CallRecord`` triggers a small ``call.completed`` event so the
wallboard updates in <2s without polling. ``FraudIncident`` rows generate a
``fraud.detected`` toast.
"""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from .consumers import group_name


def _publish(company_id: int, event_type: str, payload: dict) -> None:
    layer = get_channel_layer()
    if layer is None or company_id is None:
        return
    async_to_sync(layer.group_send)(group_name(company_id), {
        'type': 'wallboard.event',
        'event_type': event_type,
        'payload': payload,
    })


@receiver(post_save, sender='cdr3cx.CallRecord')
def _on_call_record_save(sender, instance, created, **kwargs):
    if not created or instance.company_id is None:
        return
    _publish(instance.company_id, 'call.completed', {
        'id':         instance.pk,
        'caller':     instance.caller,
        'callee':     instance.callee,
        'duration':   instance.duration,
        'category':   instance.call_category,
        'total_cost': str(instance.total_cost) if instance.total_cost is not None else None,
        'call_time':  instance.call_time.isoformat() if instance.call_time else None,
        'from_dispname': instance.from_dispname,
        'to_dispname':   instance.to_dispname,
    })


@receiver(post_save, sender='billing.FraudIncident')
def _on_fraud_incident_save(sender, instance, created, **kwargs):
    if not created or instance.company_id is None:
        return
    _publish(instance.company_id, 'fraud.detected', {
        'id':       instance.pk,
        'severity': instance.severity,
        'summary':  instance.summary,
    })
