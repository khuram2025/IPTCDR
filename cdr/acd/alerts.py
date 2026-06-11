"""ACD SLA-breach evaluation (P2.6).

Turns the genuine per-queue daily KPIs (real_queue_kpis, sourced from the 3CX
XAPI — not the IVR socket feed) into tiered amber/red breaches against each
queue's ThresholdPolicy. The Celery task in acd.tasks persists these as QueueAlert
rows (idempotent) and emails the company admin. Pure computation lives here so it
is unit-testable without the worker.
"""
from acd.kpi import format_seconds, real_queue_kpis


def resolve_company_alert_email(company):
    """Best email for a company's ACD alerts: an active company_admin, else the
    configured fallback. Mirrors cdr3cx.notification_utils for quota alerts."""
    from django.conf import settings
    from accounts.models import CustomUser

    admin = (
        CustomUser.objects.filter(company=company, role='company_admin', is_active=True)
        .exclude(email='').order_by('id').first()
    )
    if admin and admin.email:
        return admin.email
    return (getattr(settings, 'QUOTA_ALERT_FALLBACK_EMAIL', None)
            or settings.DEFAULT_FROM_EMAIL)


def _policy_for(company, queue):
    """ThresholdPolicy for a queue: queue-specific, else company default, else a
    sane built-in default. Returns a dict of the thresholds we evaluate."""
    from acd.models import ThresholdPolicy

    policy = (ThresholdPolicy.objects.filter(company=company, queue=queue, is_active=True).first()
              or ThresholdPolicy.objects.filter(company=company, queue__isnull=True, is_active=True).first())
    if policy:
        return {
            'sla_target_pct': policy.sla_target_pct,
            'amber_wait_seconds': policy.amber_wait_seconds,
            'red_wait_seconds': policy.red_wait_seconds,
        }
    return {'sla_target_pct': 80, 'amber_wait_seconds': 90, 'red_wait_seconds': 120}


def evaluate_queue_breaches(company, day):
    """Evaluate one day's real per-queue KPIs against thresholds.

    Returns a list of breach dicts: queue (Queue), metric, severity, value,
    threshold, message. Only queues that actually took calls that day are
    considered (an idle/weekend queue is not a breach). For each metric the most
    severe band that applies is emitted (red supersedes amber).
    """
    rq = real_queue_kpis(company, day, day)
    if not rq['available']:
        return []

    # Index the per-queue rows back to Queue objects by DN.
    from acd.models import Queue
    queues_by_dn = {
        q.external_id: q
        for q in Queue.objects.filter(company=company, is_acd_queue=True)
    }

    breaches = []
    for row in rq['per_queue']:
        if not row['calls']:
            continue
        queue = queues_by_dn.get(row['dn'])
        if not queue:
            continue
        th = _policy_for(company, queue)

        # 1) Answer rate below SLA target percentage.
        ar = row['answer_rate']
        target = th['sla_target_pct']
        if ar < target:
            sev = 'red' if ar < target / 2 else 'amber'
            breaches.append({
                'queue': queue, 'metric': 'answer_rate', 'severity': sev,
                'value': ar, 'threshold': target,
                'message': (f"{queue.name} answered {ar}% of {row['calls']} calls "
                            f"(target {target}%)"),
            })

        # 2) ASA (speed of answer) above wait thresholds.
        asa = row['asa_seconds']
        if asa is not None:
            if asa >= th['red_wait_seconds']:
                breaches.append({
                    'queue': queue, 'metric': 'asa', 'severity': 'red',
                    'value': asa, 'threshold': th['red_wait_seconds'],
                    'message': (f"{queue.name} ASA {format_seconds(asa)} "
                                f"(red >= {format_seconds(th['red_wait_seconds'])})"),
                })
            elif asa >= th['amber_wait_seconds']:
                breaches.append({
                    'queue': queue, 'metric': 'asa', 'severity': 'amber',
                    'value': asa, 'threshold': th['amber_wait_seconds'],
                    'message': (f"{queue.name} ASA {format_seconds(asa)} "
                                f"(amber >= {format_seconds(th['amber_wait_seconds'])})"),
                })

        # 3) Longest abandon wait above wait thresholds.
        maw = row['max_abandon_wait_seconds']
        if maw is not None and row['abandon_count']:
            if maw >= th['red_wait_seconds']:
                breaches.append({
                    'queue': queue, 'metric': 'abandon_wait', 'severity': 'red',
                    'value': maw, 'threshold': th['red_wait_seconds'],
                    'message': (f"{queue.name} {row['abandon_count']} abandoned, longest "
                                f"wait {format_seconds(maw)} (red >= "
                                f"{format_seconds(th['red_wait_seconds'])})"),
                })
            elif maw >= th['amber_wait_seconds']:
                breaches.append({
                    'queue': queue, 'metric': 'abandon_wait', 'severity': 'amber',
                    'value': maw, 'threshold': th['amber_wait_seconds'],
                    'message': (f"{queue.name} {row['abandon_count']} abandoned, longest "
                                f"wait {format_seconds(maw)} (amber >= "
                                f"{format_seconds(th['amber_wait_seconds'])})"),
                })

    return breaches
