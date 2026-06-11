"""Alert rules engine (P4.4).

Generalises the ACD-only SLA alerting (P2.6) into a tenant-configurable engine:
AlertRules subscribe to an event source (fraud / acd_sla / quota), filter by
severity, and fan out to channels (email today; sms/whatsapp are pluggable stubs
that record intent) with optional time-based escalation. Each dispatch is logged as
an AlertEvent. Bounded per run so a backlog (e.g. 18k fraud incidents) drains
gradually rather than blasting at once.
"""
import logging

from django.utils import timezone

from notifications.models import AlertRule, AlertEvent

logger = logging.getLogger(__name__)

MAX_PER_RUN = 100


# --- channel dispatch ------------------------------------------------------ #
def _send_email(recipients, subject, body):
    from notifications.utils import send_notification_email
    ok = True
    for r in recipients:
        try:
            send_notification_email(r, subject, body)
        except Exception as e:
            logger.warning('alert email to %s failed: %s', r, e)
            ok = False
    return ok


def _send_sms(recipients, subject, body):
    # Pluggable stub — wire a real SMS gateway here. Records intent for now.
    logger.info('SMS alert (stub) to %s: %s', recipients, subject)
    return False


def _send_whatsapp(recipients, subject, body):
    logger.info('WhatsApp alert (stub) to %s: %s', recipients, subject)
    return False


_CHANNELS = {'email': _send_email, 'sms': _send_sms, 'whatsapp': _send_whatsapp}


def dispatch(rule, recipients, subject, body):
    """Send across a rule's channels. Returns (channels_sent_list, any_delivered)."""
    sent, delivered = [], False
    for ch in rule.channel_list():
        fn = _CHANNELS.get(ch)
        if not fn:
            continue
        ok = fn(recipients, subject, body)
        sent.append(ch)
        delivered = delivered or ok
    return sent, delivered


# --- sources --------------------------------------------------------------- #
def _rules_for(source):
    return list(AlertRule.objects.filter(source=source, is_active=True))


def run_fraud_alerts():
    """Dispatch alerts for open, undispatched FraudIncidents matching a rule."""
    from billing.models import FraudIncident

    rules = _rules_for(AlertRule.SOURCE_FRAUD)
    if not rules:
        return 0
    fired = 0
    qs = (FraudIncident.objects.filter(status='open', notification_dispatched=False)
          .select_related('company').order_by('-detected_at')[:MAX_PER_RUN])
    for inc in qs:
        rule = next((r for r in rules
                     if (r.company_id in (None, inc.company_id))
                     and r.severity_ge(inc.severity)), None)
        if not rule:
            continue
        recips = rule.recipient_list()
        subject = f"[FRAUD {inc.severity.upper()}] {inc.summary[:90]}"
        body = f"{inc.summary}\nCompany: {inc.company.name}\nDetected: {inc.detected_at}"
        sent, delivered = dispatch(rule, recips, subject, body)
        AlertEvent.objects.create(
            rule=rule, company=inc.company, source='fraud', severity=inc.severity,
            summary=inc.summary[:255], reference=str(inc.pk),
            channels_sent=','.join(sent), delivered=delivered)
        inc.notification_dispatched = True
        inc.save(update_fields=['notification_dispatched'])
        fired += 1
    return fired


def run_acd_sla_alerts():
    """Mirror recent QueueAlerts (P2.6) into the generic engine for tenants that
    configured an acd_sla rule with extra channels/escalation."""
    from datetime import timedelta
    from acd.models import QueueAlert

    rules = _rules_for(AlertRule.SOURCE_ACD_SLA)
    if not rules:
        return 0
    since = timezone.now() - timedelta(hours=24)
    fired = 0
    seen = set(AlertEvent.objects.filter(source='acd_sla', created_at__gte=since)
               .values_list('reference', flat=True))
    for qa in (QueueAlert.objects.filter(created_at__gte=since)
               .select_related('queue', 'queue__company')[:MAX_PER_RUN]):
        if str(qa.pk) in seen:
            continue
        company = qa.queue.company
        rule = next((r for r in rules
                     if (r.company_id in (None, company.id))
                     and r.severity_ge(qa.severity)), None)
        if not rule:
            continue
        subject = f"[ACD {qa.severity.upper()}] {qa.message[:90]}"
        sent, delivered = dispatch(rule, rule.recipient_list(), subject, qa.message)
        AlertEvent.objects.create(
            rule=rule, company=company, source='acd_sla', severity=qa.severity,
            summary=qa.message[:255], reference=str(qa.pk),
            channels_sent=','.join(sent), delivered=delivered)
        fired += 1
    return fired


def run_escalations():
    """Escalate AlertEvents that are older than their rule's window and not yet
    escalated, to the rule's escalation recipients."""
    from datetime import timedelta
    fired = 0
    candidates = (AlertEvent.objects.filter(escalated=False, rule__isnull=False)
                  .select_related('rule', 'company')
                  .filter(rule__escalate_after_minutes__gt=0)[:MAX_PER_RUN])
    now = timezone.now()
    for ev in candidates:
        window = timedelta(minutes=ev.rule.escalate_after_minutes)
        if now - ev.created_at < window:
            continue
        recips = ev.rule.recipient_list(escalation=True)
        if recips:
            dispatch(ev.rule, recips, f"[ESCALATION] {ev.summary[:90]}", ev.summary)
        ev.escalated = True
        ev.escalated_at = now
        ev.save(update_fields=['escalated', 'escalated_at'])
        fired += 1
    return fired


def run_survey_csat_alerts():
    """Alert when rolling 24h CSAT falls below the campaign target."""
    from datetime import timedelta
    from surveys.services.metrics import compute_csat
    from surveys.models import SurveyCampaign

    rules = _rules_for(AlertRule.SOURCE_SURVEY_CSAT)
    if not rules:
        return 0
    since = timezone.localdate() - timedelta(days=1)
    today = timezone.localdate()
    fired = 0
    seen = set(
        AlertEvent.objects.filter(source='survey_csat', created_at__gte=timezone.now() - timedelta(hours=24))
        .values_list('reference', flat=True)
    )
    for camp in SurveyCampaign.objects.filter(is_active=True, license_verified=True).select_related('company'):
        company = camp.company
        if not company.surveys_available:
            continue
        csat = compute_csat(company, since, today)
        if csat['csat_pct'] is None or csat['rating_count'] < 3:
            continue
        if csat['csat_pct'] >= camp.csat_target_pct:
            continue
        ref = f'{company.id}:{camp.id}:{today}'
        if ref in seen:
            continue
        rule = next((r for r in rules if r.company_id in (None, company.id)), None)
        if not rule:
            continue
        summary = f'CSAT {csat["csat_pct"]}% below target {camp.csat_target_pct}% ({csat["rating_count"]} ratings)'
        subject = f'[CSAT] {company.name}: {summary}'
        sent, delivered = dispatch(rule, rule.recipient_list(), subject, summary)
        AlertEvent.objects.create(
            rule=rule, company=company, source='survey_csat', severity='amber',
            summary=summary[:255], reference=ref,
            channels_sent=','.join(sent), delivered=delivered,
        )
        fired += 1
    return fired


def run_all():
    return {
        'fraud': run_fraud_alerts(),
        'acd_sla': run_acd_sla_alerts(),
        'survey_csat': run_survey_csat_alerts(),
        'escalated': run_escalations(),
    }
