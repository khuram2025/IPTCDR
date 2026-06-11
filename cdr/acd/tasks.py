"""ACD enrichment + entity-linking Celery tasks.

These run on the Celery worker (stood up in P0.6) so the hot CDR ingest path is
never touched. `enrich_pending_callrecords` is scheduled by celery-beat to pick up
newly ingested rows (direction IS NULL) and populate the derived ACD columns plus
the queue/agent foreign keys.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def link_entities(record):
    """Resolve (queue_id, agent_id) for a CallRecord from its 3CX DNs.

    Queue.external_id == CallRecord.to_dn (the IVR/queue DN the call hit).
    Agent.external_id == CallRecord.final_dn (the extension that finally answered).
    Returns (queue_id|None, agent_id|None); never raises.
    """
    from acd.models import Queue, Agent

    queue_id = None
    agent_id = None
    to_dn = (record.to_dn or '').strip()
    final_dn = (record.final_dn or '').strip()
    if to_dn:
        queue_id = (
            Queue.objects.filter(company_id=record.company_id, external_id=to_dn)
            .values_list('id', flat=True).first()
        )
    if final_dn:
        agent_id = (
            Agent.objects.filter(company_id=record.company_id, external_id=final_dn)
            .values_list('id', flat=True).first()
        )
    return queue_id, agent_id


_ENRICH_FIELDS = [
    'direction', 'ring_time', 'wait_time', 'abandoned',
    'call_disposition', 'queue_id', 'agent_id',
]


@shared_task
def enrich_pending_callrecords(batch_size=1000, max_batches=50):
    """Enrich + link CallRecords that ingestion left raw (direction IS NULL).

    Idempotent: enrich_call_record always sets `direction` to a non-null value, so
    a processed row is never picked up again. Bounded per run by max_batches.
    """
    from cdr3cx.models import CallRecord
    from acd.derivations import enrich_call_record

    processed = 0
    for _ in range(max_batches):
        batch = list(
            CallRecord.objects.filter(direction__isnull=True).order_by('id')[:batch_size]
        )
        if not batch:
            break
        for rec in batch:
            enrich_call_record(rec)
            rec.queue_id, rec.agent_id = link_entities(rec)
            if not rec.ingest_transport:
                rec.ingest_transport = 'socket'
        CallRecord.objects.bulk_update(batch, _ENRICH_FIELDS + ['ingest_transport'], batch_size=500)
        processed += len(batch)

    if processed:
        logger.info('enrich_pending_callrecords processed %s rows', processed)
    return processed


# ---------------------------------------------------------------------------
# P1.3 — 3CX XAPI queue-performance pull (real ASA/SLA, not the socket feed)
# ---------------------------------------------------------------------------
def _xapi_client(company, verify_tls=True):
    from acd.sources.threecx_xapi import ThreeCXXapiClient
    if not (company.pbx_api_url and company.pbx_api_user and company.pbx_api_password):
        return None
    return ThreeCXXapiClient(
        company.pbx_api_url, company.pbx_api_user, company.pbx_api_password,
        verify_tls=verify_tls,
    )


def ensure_real_queues(company, client):
    """Upsert acd.Queue rows for the tenant's real 3CX queues. Returns {dn: Queue}."""
    from acd.models import Queue
    result = {}
    for number, name in client.list_queues():
        q, _ = Queue.objects.update_or_create(
            company=company, source_pbx='3cx', external_id=str(number),
            defaults={'name': (name or f'Queue {number}')[:128], 'is_acd_queue': True},
        )
        result[str(number)] = q
    return result


def _upsert_abandoned_calls(client, queues, dns, start, end):
    """Pull abandoned-queue calls for [start, end] and upsert one row per call.

    The 3CX report returns a header row (call_time set) plus per-agent polling
    subrows (call_time None) for the same CallHistoryId; we keep header rows only,
    so each QueueAbandonedCall is exactly one abandoned call. Idempotent.
    """
    from django.utils.dateparse import parse_datetime
    from acd.models import QueueAbandonedCall

    n = 0
    for r in client.abandoned_queue_calls(dns, start, end):
        if not r['call_time'] or not r['external_id']:
            continue  # skip polling subrows / unidentifiable rows
        q = queues.get(r['queue_dn'])
        if not q:
            continue
        when = parse_datetime(r['call_time'])
        if when is None:
            continue
        QueueAbandonedCall.objects.update_or_create(
            queue=q, external_id=r['external_id'],
            defaults={
                'call_time': when,
                'wait_seconds': r['wait_seconds'],
                'caller_id': r['caller_id'],
                'last_agent_dn': r['agent_dn'],
                'last_agent_name': r['agent_name'],
                'polling_attempts': r['polling_attempts'],
                'was_logged_in': r['was_logged_in'],
                'source': '3cx_xapi',
            },
        )
        n += 1
    return n


def _upsert_agent_stats(client, queues, dns, day, start, end):
    """Pull per-agent in-queue stats for the day and upsert AgentQueueDailyStats."""
    from acd.models import AgentQueueDailyStats

    n = 0
    for r in client.agents_in_queue_statistics(dns, start, end):
        q = queues.get(r['queue_dn'])
        if not q or not r['agent_dn']:
            continue
        AgentQueueDailyStats.objects.update_or_create(
            queue=q, agent_dn=r['agent_dn'], stat_date=day,
            defaults={
                'agent_name': r['agent_name'],
                'answered': r['answered'], 'lost': r['lost'],
                'answered_pct': r['answered_pct'],
                'logged_in_seconds': r['logged_in_seconds'],
                'ring_time_seconds': r['ring_time_seconds'],
                'avg_ring_seconds': r['avg_ring_seconds'],
                'talk_time_seconds': r['talk_time_seconds'],
                'avg_talk_seconds': r['avg_talk_seconds'],
                'source': '3cx_xapi',
            },
        )
        n += 1
    return n


@shared_task
def pull_3cx_queue_stats(company_id=None, days_back=2, verify_tls=True):
    """Pull per-queue daily ACD stats from the 3CX XAPI into QueueDailyStats.

    Runs on the worker. Idempotent via update_or_create on (queue, stat_date).
    Default days_back=2 keeps yesterday/today fresh; a larger value backfills.
    """
    from datetime import datetime, timedelta, time as dt_time, timezone as dt_timezone
    from django.utils import timezone
    from accounts.models import Company
    from acd.models import QueueDailyStats

    companies = Company.objects.exclude(pbx_api_url='')
    if company_id:
        companies = companies.filter(pk=company_id)

    summary = {'queue_days': 0, 'abandoned': 0, 'agent_days': 0}
    for company in companies:
        client = _xapi_client(company, verify_tls=verify_tls)
        if not client:
            continue
        try:
            queues = ensure_real_queues(company, client)
        except Exception as e:
            logger.warning('pull_3cx_queue_stats: %s queue list failed: %s', company.name, e)
            continue
        dns = list(queues.keys())
        if not dns:
            continue

        today = timezone.localdate()
        for n in range(days_back):
            day = today - timedelta(days=n)
            start = timezone.make_aware(datetime.combine(day, dt_time.min))
            end = start + timedelta(days=1)
            start_utc = start.astimezone(dt_timezone.utc)
            end_utc = end.astimezone(dt_timezone.utc)
            try:
                rows = client.detailed_queue_statistics(dns, start_utc, end_utc)
            except Exception as e:
                logger.warning('pull_3cx_queue_stats: %s %s stats failed: %s', company.name, day, e)
                continue
            for r in rows:
                q = queues.get(r['queue_dn'])
                if not q:
                    continue
                QueueDailyStats.objects.update_or_create(
                    queue=q, stat_date=day,
                    defaults={
                        'calls': r['calls'], 'answered': r['answered'],
                        'ring_time_seconds': r['ring_time_seconds'],
                        'talk_time_seconds': r['talk_time_seconds'],
                        'avg_ring_seconds': r['avg_ring_seconds'],
                        'avg_talk_seconds': r['avg_talk_seconds'],
                        'callbacks': r['callbacks'], 'source': '3cx_xapi',
                    },
                )
                summary['queue_days'] += 1

            # Agent-side + true-abandonment detail (same window). Non-fatal per kind.
            try:
                summary['abandoned'] += _upsert_abandoned_calls(
                    client, queues, dns, start_utc, end_utc)
            except Exception as e:
                logger.warning('pull_3cx_queue_stats: %s %s abandoned failed: %s',
                               company.name, day, e)
            try:
                summary['agent_days'] += _upsert_agent_stats(
                    client, queues, dns, day, start_utc, end_utc)
            except Exception as e:
                logger.warning('pull_3cx_queue_stats: %s %s agent stats failed: %s',
                               company.name, day, e)

    if any(summary.values()):
        logger.info('pull_3cx_queue_stats upserted %s', summary)
    return summary


# ---------------------------------------------------------------------------
# P2.6 — SLA-breach alerting on the real (XAPI) queue KPIs
# ---------------------------------------------------------------------------
def _send_alert_email(recipient, severity, message):
    """Best-effort email; never raises (SMTP creds may be unset). Returns bool.

    The QueueAlert row is the durable audit trail, so we only send the email here.
    We deliberately do NOT create a notifications.Notification: that table has a
    NOT NULL notification_type column the current Notification model doesn't declare
    (schema/model drift), so ORM creates raise — and its post_save signal would
    duplicate the send anyway. send_notification_email wraps Django send_mail.
    """
    from notifications.utils import send_notification_email

    subject = f"[ACD {severity.upper()}] {message[:120]}"
    try:
        send_notification_email(recipient, subject, message)
        return True
    except Exception as e:  # SMTP down / no creds — QueueAlert still records the breach
        logger.warning('SLA alert email to %s failed: %s', recipient, e)
        return False


@shared_task
def check_queue_sla_breaches(company_id=None, day=None):
    """Evaluate one day's real ACD KPIs per queue and fire tiered amber/red alerts.

    Idempotent: a QueueAlert is unique on (queue, day, metric, severity), so re-runs
    never re-email the same breach, while an amber->red escalation creates a new row
    and a fresh email. Defaults to *yesterday* (a complete day of pulled stats).
    Returns {'breaches': n, 'new': m, 'emailed': k}.
    """
    from datetime import timedelta
    from django.utils import timezone
    from django.utils.dateparse import parse_date
    from accounts.models import Company
    from acd.models import QueueAlert
    from acd.alerts import evaluate_queue_breaches, resolve_company_alert_email

    if day is None:
        day = timezone.localdate() - timedelta(days=1)
    elif isinstance(day, str):
        day = parse_date(day)

    companies = Company.objects.exclude(pbx_api_url='')
    if company_id:
        companies = companies.filter(pk=company_id)

    stats = {'breaches': 0, 'new': 0, 'emailed': 0}
    for company in companies:
        breaches = evaluate_queue_breaches(company, day)
        if not breaches:
            continue
        recipient = resolve_company_alert_email(company)
        for b in breaches:
            stats['breaches'] += 1
            alert, created = QueueAlert.objects.get_or_create(
                queue=b['queue'], stat_date=day, metric=b['metric'], severity=b['severity'],
                defaults={
                    'value': b['value'], 'threshold': b['threshold'],
                    'message': b['message'][:255], 'recipient': recipient,
                },
            )
            if not created:
                continue  # already alerted for this queue/day/metric/severity
            stats['new'] += 1
            if _send_alert_email(recipient, b['severity'], b['message']):
                stats['emailed'] += 1
            alert.notified = True
            alert.save(update_fields=['notified'])

    if stats['breaches']:
        logger.info('check_queue_sla_breaches %s -> %s', day, stats)
    return stats


# ---------------------------------------------------------------------------
# P3.1 — Scheduled report engine
# ---------------------------------------------------------------------------
def _reports_dir(company_id):
    import os
    from django.conf import settings
    d = os.path.join(str(settings.BASE_DIR), 'generated_reports', str(company_id))
    os.makedirs(d, exist_ok=True)
    return d


def generate_report_file(company, report_type, window, fmt, scheduled_report=None):
    """Build + render a report, write it to disk, and record a ReportRun.

    Returns the ReportRun (status success/failed). Never raises — failures are
    captured on the run row so the scheduler/UI can surface them.
    """
    import os
    from django.utils import timezone
    from acd.models import ReportRun
    from acd.reports import build_report, render_report, resolve_window

    run = ReportRun(
        scheduled_report=scheduled_report, company=company,
        report_type=report_type, window=window, fmt=fmt,
    )
    try:
        start, end = resolve_window(window)
        data = build_report(report_type, company, start, end)
        content, _mime, ext = render_report(data, fmt)
        stamp = timezone.localtime().strftime('%Y%m%d-%H%M%S')
        fname = f'{report_type}_{window}_{stamp}.{ext}'
        path = os.path.join(_reports_dir(company.id), fname)
        with open(path, 'wb') as fh:
            fh.write(content)
        run.status = ReportRun.STATUS_SUCCESS
        run.filename = fname
        run.file_path = path
        run.row_count = len(data['rows'])
    except Exception as e:
        run.status = ReportRun.STATUS_FAILED
        run.error = str(e)[:2000]
        logger.exception('generate_report_file failed: %s/%s/%s', report_type, window, fmt)
    run.save()
    return run


def _email_report_run(run, recipients):
    """Email a generated report file as an attachment. Returns True on send."""
    from django.conf import settings
    from django.core.mail import EmailMessage
    from acd.reports import _MIME

    subject = f"[Report] {run.get_report_type_display() if hasattr(run, 'get_report_type_display') else run.report_type} — {run.company.name} ({run.window})"
    body = (f"Attached: {run.filename}\n\nReport: {run.report_type}\n"
            f"Window: {run.window}\nRows: {run.row_count}\n")
    try:
        with open(run.file_path, 'rb') as fh:
            content = fh.read()
        msg = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, recipients)
        msg.attach(run.filename, content, _MIME.get(run.fmt, 'application/octet-stream'))
        msg.send(fail_silently=False)
        return True
    except Exception as e:
        logger.warning('emailing report run %s failed: %s', run.id, e)
        return False


@shared_task
def run_scheduled_report(report_id, reschedule=True):
    """Generate one ScheduledReport, email it, and (optionally) advance next_run_at."""
    from django.utils import timezone
    from acd.models import ScheduledReport

    try:
        sr = ScheduledReport.objects.select_related('company').get(pk=report_id)
    except ScheduledReport.DoesNotExist:
        return {'error': 'not found'}

    run = generate_report_file(sr.company, sr.report_type, sr.window, sr.fmt, scheduled_report=sr)
    recipients = sr.recipient_list()
    if run.status == 'success' and recipients:
        run.recipients = ', '.join(recipients)[:512]
        run.emailed = _email_report_run(run, recipients)
        run.save(update_fields=['recipients', 'emailed'])

    sr.last_run_at = timezone.now()
    if reschedule:
        sr.next_run_at = sr.compute_next_run()
    sr.save(update_fields=['last_run_at', 'next_run_at'])
    return {'run_id': run.id, 'status': run.status, 'emailed': run.emailed,
            'rows': run.row_count}


@shared_task
def run_due_scheduled_reports():
    """Beat task: run every active ScheduledReport whose next_run_at is due."""
    from django.utils import timezone
    from acd.models import ScheduledReport

    now = timezone.now()
    ran = 0
    for sr in ScheduledReport.objects.filter(is_active=True):
        if sr.next_run_at is None:
            sr.next_run_at = sr.compute_next_run()  # initialise; don't fire immediately
            sr.save(update_fields=['next_run_at'])
            continue
        if sr.next_run_at <= now:
            run_scheduled_report(sr.id)
            ran += 1
    if ran:
        logger.info('run_due_scheduled_reports ran %s report(s)', ran)
    return {'ran': ran}


@shared_task
def purge_old_report_files(days=None):
    """Delete generated report files older than REPORT_RETENTION_DAYS and blank the
    stored path on their ReportRun rows (the run record stays as audit)."""
    import os
    from datetime import timedelta
    from django.conf import settings
    from django.utils import timezone
    from acd.models import ReportRun

    days = days if days is not None else getattr(settings, 'REPORT_RETENTION_DAYS', 30)
    cutoff = timezone.now() - timedelta(days=days)
    removed = 0
    for run in ReportRun.objects.filter(created_at__lt=cutoff).exclude(file_path=''):
        try:
            if run.file_path and os.path.exists(run.file_path):
                os.remove(run.file_path)
                removed += 1
        except OSError as e:
            logger.warning('purge_old_report_files: %s: %s', run.file_path, e)
        run.file_path = ''
        run.save(update_fields=['file_path'])
    if removed:
        logger.info('purge_old_report_files removed %s file(s) older than %sd', removed, days)
    return {'removed': removed}


# ---------------------------------------------------------------------------
# P3.5 — Materialized daily rollups
# ---------------------------------------------------------------------------
@shared_task
def rebuild_call_rollups(company_id=None, days_back=35):
    """Rebuild the recent CallDailyRollup window. Beat runs this nightly with a
    rolling window; a full rebuild uses the management command with a large
    days_back."""
    from acd.rollups import build_call_rollups
    return {'upserts': build_call_rollups(company_id=company_id, days_back=days_back)}


@shared_task
def run_alert_rules():
    """P4.4 — evaluate the tenant alert-rules engine across all sources + escalate.
    No-ops entirely until an AlertRule is configured."""
    from notifications.alert_engine import run_all
    return run_all()


# ---------------------------------------------------------------------------
# 3CX XAPI user/extension sync (one-way PBX -> local accounts.Extension)
# ---------------------------------------------------------------------------
@shared_task
def sync_3cx_users(company_id=None, verify_tls=True):
    """Sync real user extensions from each tenant's 3CX into accounts.Extension.

    One-way (read-only to the PBX) and idempotent: upsert keyed by
    (company, extension). NEVER deletes -- a hard delete would cascade-wipe the
    extension's UserQuota balance -- so extensions that disappear from 3CX are
    soft-deactivated (is_active=False). /xapi/v1/Users returns only real users
    (queues/IVRs/ring groups are separate object types). Returns a per-company
    summary dict. Companies without pbx_api_* are skipped.
    """
    from django.utils import timezone
    from accounts.models import Company, Extension

    companies = Company.objects.exclude(pbx_api_url='')
    if company_id:
        companies = companies.filter(pk=company_id)

    summary = {}
    for company in companies:
        client = _xapi_client(company, verify_tls=verify_tls)
        if not client:
            continue
        try:
            users = client.list_users()
        except Exception as e:
            logger.warning('sync_3cx_users: %s user list failed: %s', company.name, e)
            summary[company.name] = {'error': str(e)[:200]}
            continue

        now = timezone.now()
        created = updated = failed = 0
        seen = set()
        for u in users:
            number = u['number']
            seen.add(number)
            full_name = (f"{u['first_name']} {u['last_name']}".strip()
                         or u['display_name'] or '').strip()
            defaults = {
                'first_name': (u['first_name'][:30] or None),
                'last_name': (u['last_name'][:30] or None),
                'full_name': (full_name[:100] or None),
                'email': (u['email'][:254] or None),
                'display_name': u['display_name'][:128],
                'mobile': u['mobile'][:32],
                'outbound_caller_id': u['outbound_caller_id'][:32],
                'enabled': u['enabled'],
                'is_registered': u['is_registered'],
                'disable_external_call': u['internal'],
                'pbx_user_id': u['pbx_id'],
                'is_active': True,
                'last_synced_at': now,
                'source_pbx': '3cx',
            }
            try:
                _, was_created = Extension.objects.update_or_create(
                    company=company, extension=number, defaults=defaults,
                )
                created += int(was_created)
                updated += int(not was_created)
            except Exception as e:
                failed += 1
                logger.warning('sync_3cx_users: %s ext %s failed: %s',
                               company.name, number, e)

        # Soft-deactivate 3cx-sourced extensions that vanished from the PBX.
        deactivated = (
            Extension.objects.filter(company=company, source_pbx='3cx', is_active=True)
            .exclude(extension__in=seen)
            .update(is_active=False)
        )
        summary[company.name] = {
            'pulled': len(users), 'created': created, 'updated': updated,
            'failed': failed, 'deactivated': deactivated,
        }
        logger.info('sync_3cx_users: %s -> %s', company.name, summary[company.name])
    return summary
