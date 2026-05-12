"""Webhook fan-out + HMAC-signed delivery.

Synchronous delivery for now (Phase 1) — wraps cleanly into a Celery task in
Phase 1 W1 (DevOps). To upgrade, replace ``deliver_now`` with ``deliver.delay``
and decorate with ``@shared_task``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import timedelta

import requests
from django.utils import timezone

from ..models import WebhookDelivery, WebhookSubscription

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 4
RETRY_BACKOFF_SECONDS = [0, 60, 600, 3600]  # immediate, 1m, 10m, 1h
DELIVERY_TIMEOUT = 8


def sign(secret: str, body: bytes) -> str:
    """Return ``sha256=<hex>`` signature."""
    digest = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
    return f'sha256={digest}'


def fan_out(company, event_type: str, payload: dict) -> list[WebhookDelivery]:
    """Create WebhookDelivery rows for every active subscription matching event_type."""
    subs = WebhookSubscription.objects.filter(
        company=company, is_active=True,
    )
    deliveries = []
    for sub in subs:
        if sub.events and event_type not in sub.events:
            continue
        delivery = WebhookDelivery.objects.create(
            subscription=sub,
            event_type=event_type,
            payload=payload,
            next_retry_at=timezone.now(),
        )
        deliveries.append(delivery)
    return deliveries


def deliver_now(delivery: WebhookDelivery) -> bool:
    """Attempt one delivery. Returns ``True`` on 2xx, else ``False``.

    Updates delivery + subscription health markers in either case.
    """
    sub = delivery.subscription
    body = json.dumps(delivery.payload, default=str).encode('utf-8')
    headers = {
        'Content-Type':            'application/json',
        'User-Agent':              'IPTPortal-Webhooks/1.0',
        'X-IPTPortal-Event':       delivery.event_type,
        'X-IPTPortal-Delivery-Id': str(delivery.pk),
        'X-IPTPortal-Signature':   sign(sub.secret, body),
    }

    delivery.attempts += 1
    try:
        resp = requests.post(sub.url, data=body, headers=headers, timeout=DELIVERY_TIMEOUT)
        delivery.last_status_code = resp.status_code
        delivery.last_response_excerpt = resp.text[:512]
        ok = 200 <= resp.status_code < 300
    except requests.RequestException as exc:
        logger.warning("Webhook delivery failed: %s", exc)
        delivery.last_status_code = 0
        delivery.last_response_excerpt = f'RequestException: {exc!s}'[:512]
        ok = False

    if ok:
        delivery.status = 'delivered'
        delivery.delivered_at = timezone.now()
        delivery.next_retry_at = None
        sub.last_success_at = timezone.now()
        sub.consecutive_failures = 0
    elif delivery.attempts >= MAX_ATTEMPTS:
        delivery.status = 'failed'
        delivery.next_retry_at = None
        sub.last_failure_at = timezone.now()
        sub.consecutive_failures += 1
    else:
        delivery.status = 'pending'
        delay = RETRY_BACKOFF_SECONDS[min(delivery.attempts, len(RETRY_BACKOFF_SECONDS) - 1)]
        delivery.next_retry_at = timezone.now() + timedelta(seconds=delay)
        sub.last_failure_at = timezone.now()
        sub.consecutive_failures += 1

    delivery.save(update_fields=['attempts', 'status', 'last_status_code',
                                 'last_response_excerpt', 'next_retry_at',
                                 'delivered_at'])
    sub.save(update_fields=['last_success_at', 'last_failure_at',
                            'consecutive_failures'])
    return ok


def emit(company, event_type: str, payload: dict) -> int:
    """Public entry point: fan out + try immediate delivery.

    Returns the number of subscriptions notified.
    """
    deliveries = fan_out(company, event_type, payload)
    for d in deliveries:
        deliver_now(d)
    return len(deliveries)
