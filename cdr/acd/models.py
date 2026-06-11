"""Vendor-neutral ACD entities for queue/agent analytics."""
from django.db import models


class Team(models.Model):
    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='acd_teams',
    )
    name = models.CharField(max_length=100)
    supervisor = models.ForeignKey(
        'accounts.CustomUser', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='supervised_teams',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company', 'name')
        ordering = ['company', 'name']

    def __str__(self):
        return f"{self.company.name} — {self.name}"


class Queue(models.Model):
    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='acd_queues',
    )
    source_pbx = models.CharField(max_length=20, default='3cx')
    external_id = models.CharField(
        max_length=128,
        help_text='Vendor queue id/DN (3CX queue extension, CUCM hunt pilot, etc.)',
    )
    name = models.CharField(max_length=128)
    is_acd_queue = models.BooleanField(
        default=False, db_index=True,
        help_text='True = a real 3CX ACD queue (XAPI-sourced, has agent-wait timing). '
                  'False = an IVR/DN-derived pseudo-queue from the socket CDR.',
    )
    team = models.ForeignKey(
        Team, null=True, blank=True, on_delete=models.SET_NULL, related_name='queues',
    )
    sla_target_seconds = models.PositiveIntegerField(default=20)
    sla_target_pct = models.PositiveIntegerField(default=80)
    short_abandon_seconds = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('company', 'source_pbx', 'external_id')
        ordering = ['company', 'name']
        indexes = [
            models.Index(fields=['company', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.external_id})"


class Agent(models.Model):
    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='acd_agents',
    )
    extension = models.ForeignKey(
        'accounts.Extension', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='acd_agent_profile',
    )
    source_pbx = models.CharField(max_length=20, default='3cx')
    external_id = models.CharField(max_length=128)
    display_name = models.CharField(max_length=128)
    team = models.ForeignKey(
        Team, null=True, blank=True, on_delete=models.SET_NULL, related_name='agents',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company', 'source_pbx', 'external_id')
        ordering = ['company', 'display_name']

    def __str__(self):
        return self.display_name or self.external_id


class QueueMembership(models.Model):
    queue = models.ForeignKey(Queue, on_delete=models.CASCADE, related_name='memberships')
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='queue_memberships')
    priority = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('queue', 'agent')

    def __str__(self):
        return f"{self.agent} → {self.queue}"


class AgentStateEvent(models.Model):
    STATE_AVAILABLE = 'available'
    STATE_RESERVED = 'reserved'
    STATE_ON_CALL = 'on_call'
    STATE_WRAP = 'wrap'
    STATE_NOT_READY = 'not_ready'
    STATE_OFFLINE = 'offline'

    STATE_CHOICES = [
        (STATE_AVAILABLE, 'Available'),
        (STATE_RESERVED, 'Reserved'),
        (STATE_ON_CALL, 'On Call'),
        (STATE_WRAP, 'Wrap'),
        (STATE_NOT_READY, 'Not Ready'),
        (STATE_OFFLINE, 'Offline'),
    ]

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='state_events')
    state = models.CharField(max_length=16, choices=STATE_CHOICES, db_index=True)
    reason_code = models.CharField(max_length=32, blank=True, default='')
    started_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['agent', '-started_at']),
        ]

    def __str__(self):
        return f"{self.agent} {self.state} @ {self.started_at:%Y-%m-%d %H:%M}"


class Disposition(models.Model):
    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='dispositions',
    )
    code = models.CharField(max_length=40)
    label = models.CharField(max_length=64)
    is_resolution = models.BooleanField(
        default=False, help_text='Counts toward operational FCR approximation',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('company', 'code')
        ordering = ['company', 'code']

    def __str__(self):
        return f"{self.code} — {self.label}"


class ThresholdPolicy(models.Model):
    """Per-tenant/per-queue SLA and alert thresholds (shared by KPIs + wallboard)."""
    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='threshold_policies',
    )
    queue = models.ForeignKey(
        Queue, null=True, blank=True, on_delete=models.CASCADE,
        related_name='threshold_policies',
        help_text='Null = company-wide default',
    )
    sla_target_seconds = models.PositiveIntegerField(default=20)
    sla_target_pct = models.PositiveIntegerField(default=80)
    short_abandon_seconds = models.PositiveIntegerField(default=10)
    amber_wait_seconds = models.PositiveIntegerField(default=90)
    red_wait_seconds = models.PositiveIntegerField(default=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('company', 'queue')
        ordering = ['company', 'queue']

    def __str__(self):
        scope = self.queue.name if self.queue else 'Company default'
        return f"{self.company.name} — {scope}"


class CallLeg(models.Model):
    LEG_INBOUND = 'inbound'
    LEG_QUEUE = 'queue'
    LEG_AGENT = 'agent'
    LEG_TRANSFER = 'transfer'

    LEG_CHOICES = [
        (LEG_INBOUND, 'Inbound'),
        (LEG_QUEUE, 'Queue'),
        (LEG_AGENT, 'Agent'),
        (LEG_TRANSFER, 'Transfer'),
    ]

    call = models.ForeignKey(
        'cdr3cx.CallRecord', on_delete=models.CASCADE, related_name='legs',
    )
    correlation_id = models.CharField(max_length=128, blank=True, default='', db_index=True)
    leg_type = models.CharField(max_length=20, choices=LEG_CHOICES)
    queue = models.ForeignKey(Queue, null=True, blank=True, on_delete=models.SET_NULL)
    agent = models.ForeignKey(Agent, null=True, blank=True, on_delete=models.SET_NULL)
    disposition = models.ForeignKey(
        Disposition, null=True, blank=True, on_delete=models.SET_NULL,
    )
    ring_sec = models.IntegerField(null=True, blank=True)
    wait_sec = models.IntegerField(null=True, blank=True)
    talk_sec = models.IntegerField(null=True, blank=True)
    hold_sec = models.IntegerField(null=True, blank=True)
    wrap_sec = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['call', 'id']

    def __str__(self):
        return f"Leg {self.leg_type} for call {self.call_id}"


class Recording(models.Model):
    call = models.ForeignKey(
        'cdr3cx.CallRecord', on_delete=models.CASCADE, related_name='recordings',
    )
    source_pbx = models.CharField(max_length=20, default='3cx')
    external_id = models.CharField(max_length=128, blank=True, default='')
    storage_url = models.CharField(max_length=512, blank=True, default='')
    duration_sec = models.IntegerField(null=True, blank=True)
    transcript = models.TextField(blank=True, default='')
    sentiment = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Recording for call {self.call_id}"


class QueueDailyStats(models.Model):
    """Per-queue, per-day ACD statistics pulled from the 3CX XAPI
    (ReportDetailedQueueStatistics). Unlike the socket CDR, this carries real
    agent-wait timing (RingTime) so Service Level / ASA are genuine. Daily
    granularity lets the dashboard aggregate any date range.
    """
    queue = models.ForeignKey(Queue, on_delete=models.CASCADE, related_name='daily_stats')
    stat_date = models.DateField(db_index=True)
    calls = models.IntegerField(default=0)
    answered = models.IntegerField(default=0)
    # Totals (aggregatable across days); averages recomputed on read.
    ring_time_seconds = models.FloatField(null=True, blank=True, help_text='Total ring/wait seconds')
    talk_time_seconds = models.FloatField(null=True, blank=True, help_text='Total talk seconds')
    avg_ring_seconds = models.FloatField(null=True, blank=True, help_text='ASA as reported by 3CX')
    avg_talk_seconds = models.FloatField(null=True, blank=True)
    callbacks = models.IntegerField(default=0)
    source = models.CharField(max_length=20, default='3cx_xapi')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('queue', 'stat_date')
        ordering = ['-stat_date']
        indexes = [models.Index(fields=['queue', 'stat_date'])]

    @property
    def abandoned(self):
        return max(0, (self.calls or 0) - (self.answered or 0))

    def __str__(self):
        return f"{self.queue.name} {self.stat_date}: {self.answered}/{self.calls}"


class QueueAbandonedCall(models.Model):
    """One ABANDONED queue call — caller hung up before any agent answered —
    pulled from the 3CX XAPI ReportAbandonedQueueCalls. Its WaitTime is the real
    seconds the caller waited before giving up (true patience / lost-opportunity),
    which the socket CDR cannot distinguish from an IVR hangup. One row per call;
    3CX returns a header row (call_time set) plus per-agent polling subrows which
    we collapse on ingest. Idempotent via (queue, external_id=CallHistoryId).
    """
    queue = models.ForeignKey(
        Queue, on_delete=models.CASCADE, related_name='abandoned_calls',
    )
    external_id = models.CharField(
        max_length=128, help_text='3CX CallHistoryId (stable per call)',
    )
    call_time = models.DateTimeField(db_index=True)
    wait_seconds = models.FloatField(
        null=True, blank=True, help_text='Seconds the caller waited before abandoning',
    )
    caller_id = models.CharField(max_length=64, blank=True, default='')
    last_agent_dn = models.CharField(max_length=32, blank=True, default='')
    last_agent_name = models.CharField(max_length=128, blank=True, default='')
    polling_attempts = models.IntegerField(
        default=0, help_text='Number of agents the call rang before it was abandoned',
    )
    was_logged_in = models.BooleanField(
        default=False, help_text='At least one agent was logged in when abandoned',
    )
    source = models.CharField(max_length=20, default='3cx_xapi')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('queue', 'external_id')
        ordering = ['-call_time']
        indexes = [models.Index(fields=['queue', 'call_time'])]

    def __str__(self):
        return f"{self.queue.name} abandon {self.caller_id} ({self.wait_seconds}s)"


class AgentQueueDailyStats(models.Model):
    """Per-agent, per-queue, per-day productivity from the 3CX XAPI
    (ReportAgentsInQueueStatistics). Gives the agent-side ACD picture the socket
    CDR cannot: logged-in time (-> occupancy), answered vs lost rings, real
    ring/talk timing. Daily granularity aggregates across any range.
    """
    queue = models.ForeignKey(
        Queue, on_delete=models.CASCADE, related_name='agent_daily_stats',
    )
    agent_dn = models.CharField(max_length=32, db_index=True)
    agent_name = models.CharField(max_length=128, blank=True, default='')
    stat_date = models.DateField(db_index=True)
    answered = models.IntegerField(default=0)
    lost = models.IntegerField(default=0, help_text='Rings to this agent that went unanswered')
    answered_pct = models.IntegerField(default=0)
    logged_in_seconds = models.FloatField(null=True, blank=True)
    ring_time_seconds = models.FloatField(null=True, blank=True)
    avg_ring_seconds = models.FloatField(null=True, blank=True)
    talk_time_seconds = models.FloatField(null=True, blank=True)
    avg_talk_seconds = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=20, default='3cx_xapi')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('queue', 'agent_dn', 'stat_date')
        ordering = ['-stat_date', 'agent_dn']
        indexes = [models.Index(fields=['queue', 'stat_date'])]

    @property
    def occupancy_pct(self):
        """Talk time as a share of logged-in time (productive-occupancy proxy)."""
        li = self.logged_in_seconds or 0
        tk = self.talk_time_seconds or 0
        return round(tk / li * 100, 1) if li else None

    def __str__(self):
        return f"{self.agent_name} @ {self.queue.name} {self.stat_date}"


class QueueAlert(models.Model):
    """A fired ACD SLA-breach alert (P2.6). One row per (queue, day, metric,
    severity) so the daily evaluation is idempotent — re-running never re-emails an
    identical breach, but an escalation (amber -> red) creates a new red row and a
    fresh notification. Also the audit trail behind the dashboard alerts panel.
    """
    SEVERITY_AMBER = 'amber'
    SEVERITY_RED = 'red'
    SEVERITY_CHOICES = [(SEVERITY_AMBER, 'Amber'), (SEVERITY_RED, 'Red')]

    METRIC_ANSWER_RATE = 'answer_rate'
    METRIC_ASA = 'asa'
    METRIC_ABANDON_WAIT = 'abandon_wait'
    METRIC_CHOICES = [
        (METRIC_ANSWER_RATE, 'Answer rate below target'),
        (METRIC_ASA, 'ASA above threshold'),
        (METRIC_ABANDON_WAIT, 'Abandon wait above threshold'),
    ]

    queue = models.ForeignKey(Queue, on_delete=models.CASCADE, related_name='alerts')
    stat_date = models.DateField(db_index=True)
    metric = models.CharField(max_length=20, choices=METRIC_CHOICES)
    severity = models.CharField(max_length=8, choices=SEVERITY_CHOICES, db_index=True)
    value = models.FloatField(help_text='Observed value that breached (seconds or %)')
    threshold = models.FloatField(help_text='Threshold it breached')
    message = models.CharField(max_length=255, blank=True, default='')
    notified = models.BooleanField(default=False, help_text='Email dispatch attempted')
    recipient = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('queue', 'stat_date', 'metric', 'severity')
        ordering = ['-stat_date', 'queue', 'metric']
        indexes = [models.Index(fields=['queue', 'stat_date'])]

    def __str__(self):
        return f"[{self.severity}] {self.queue.name} {self.metric} {self.stat_date}"


# ---------------------------------------------------------------------------
# P3.1 — Scheduled report engine
# ---------------------------------------------------------------------------
class ScheduledReport(models.Model):
    """A recurring report definition (P3.1). The celery-beat task generates it on
    schedule, emails the rendered file to the recipients, and logs a ReportRun.

    report_type keys must match acd.reports.REPORT_TYPES; window keys must match
    acd.reports.WINDOWS — kept as plain strings here to avoid a circular import.
    """
    REPORT_TYPE_CHOICES = [
        ('callcenter_summary', 'Call Center Summary'),
        ('queue_performance', 'Queue Performance (real ACD)'),
        ('agent_productivity', 'Agent Productivity'),
        ('sla_breaches', 'SLA Breach Alerts'),
        ('daily_volume', 'Daily Call Volume'),
        ('cost_by_extension', 'Cost by Extension'),
        ('missed_calls_detail', 'Missed Calls Detail'),
        ('survey_summary', 'Survey Summary (CSAT)'),
    ]
    WINDOW_CHOICES = [
        ('yesterday', 'Yesterday'),
        ('last_7_days', 'Last 7 days'),
        ('last_30_days', 'Last 30 days'),
        ('week_to_date', 'Week to date'),
        ('month_to_date', 'Month to date'),
        ('last_month', 'Last month'),
    ]
    FORMAT_CHOICES = [('csv', 'CSV'), ('xlsx', 'Excel'), ('pdf', 'PDF'), ('html', 'HTML')]
    RECURRENCE_CHOICES = [('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')]
    WEEKDAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
        (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]

    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='scheduled_reports')
    name = models.CharField(max_length=120)
    report_type = models.CharField(max_length=32, choices=REPORT_TYPE_CHOICES)
    window = models.CharField(max_length=20, choices=WINDOW_CHOICES, default='yesterday')
    fmt = models.CharField(max_length=8, choices=FORMAT_CHOICES, default='xlsx',
                           verbose_name='Format')
    recurrence = models.CharField(max_length=10, choices=RECURRENCE_CHOICES, default='daily')
    hour = models.PositiveSmallIntegerField(default=8, help_text='Hour of day (0-23), tenant timezone')
    minute = models.PositiveSmallIntegerField(default=0)
    weekday = models.PositiveSmallIntegerField(
        choices=WEEKDAY_CHOICES, default=0, help_text='For weekly recurrence')
    day_of_month = models.PositiveSmallIntegerField(
        default=1, help_text='For monthly recurrence (1-28)')
    recipients = models.TextField(help_text='Email addresses, comma or newline separated')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        'accounts.CustomUser', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='scheduled_reports')
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['company', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()}, {self.recurrence})"

    def recipient_list(self):
        import re
        return [e.strip() for e in re.split(r'[,;\n]+', self.recipients or '') if e.strip()]

    def compute_next_run(self, after=None):
        """Next fire time strictly after `after` (default now), in tenant tz."""
        import calendar
        from datetime import timedelta
        from django.utils import timezone

        local = timezone.localtime(after or timezone.now())
        cand = local.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)

        def set_dom(dt, dom):
            return dt.replace(day=min(dom, calendar.monthrange(dt.year, dt.month)[1]))

        if self.recurrence == 'daily':
            if cand <= local:
                cand += timedelta(days=1)
        elif self.recurrence == 'weekly':
            cand += timedelta(days=(self.weekday - cand.weekday()) % 7)
            if cand <= local:
                cand += timedelta(days=7)
        else:  # monthly
            cand = set_dom(cand, self.day_of_month)
            if cand <= local:
                year = cand.year + (1 if cand.month == 12 else 0)
                month = 1 if cand.month == 12 else cand.month + 1
                cand = set_dom(cand.replace(year=year, month=month), self.day_of_month)
        return cand


class ReportRun(models.Model):
    """Audit + downloadable artifact for one generated report (scheduled or ad-hoc)."""
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [(STATUS_SUCCESS, 'Success'), (STATUS_FAILED, 'Failed')]

    scheduled_report = models.ForeignKey(
        ScheduledReport, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='runs')
    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='report_runs')
    report_type = models.CharField(max_length=32)
    window = models.CharField(max_length=20)
    fmt = models.CharField(max_length=8)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    filename = models.CharField(max_length=255, blank=True, default='')
    file_path = models.CharField(max_length=512, blank=True, default='')
    row_count = models.IntegerField(default=0)
    recipients = models.CharField(max_length=512, blank=True, default='')
    emailed = models.BooleanField(default=False)
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', '-created_at'])]

    def __str__(self):
        return f"{self.report_type} {self.fmt} @ {self.created_at:%Y-%m-%d %H:%M} ({self.status})"


# ---------------------------------------------------------------------------
# P3.5 — Materialized daily rollups (keep date-range dashboards fast at scale)
# ---------------------------------------------------------------------------
class CallDailyRollup(models.Model):
    """Pre-aggregated per-company, per-day call-center volume. The dashboard's
    daily trends + top counts read these instead of scanning ~1.49M CallRecords on
    every load. Rebuilt nightly (and on a rolling recent window) from CallRecord
    using the same case-insensitive call-center filters, so it is reconcilable and
    fully rebuildable — never a source of truth, just a cache.
    """
    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='call_rollups')
    day = models.DateField(db_index=True)
    cc_total = models.IntegerField(default=0, help_text='Call-center calls offered')
    cc_answered = models.IntegerField(default=0)
    cc_missed = models.IntegerField(default=0)
    total_talk_seconds = models.BigIntegerField(default=0)
    source = models.CharField(max_length=20, default='callrecord')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('company', 'day')
        ordering = ['-day']
        indexes = [models.Index(fields=['company', 'day'])]

    @property
    def answer_rate(self):
        return round(self.cc_answered / self.cc_total * 100, 1) if self.cc_total else 0

    def __str__(self):
        return f"{self.company_id} {self.day}: {self.cc_answered}/{self.cc_total}"
