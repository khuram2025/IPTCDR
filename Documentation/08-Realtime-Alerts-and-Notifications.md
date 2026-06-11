# Real-time, Alerts & Notifications

This document audits the platform's real-time and notification stack — the Channels/Redis wallboard (`realtime` app), the `notifications` app, the quota/fraud email paths, and the public API + webhook subsystem (`api` app) — and explains why every "scheduled" or "async" capability is effectively dead in production. It then specifies a target event-driven design: ingestion emits domain events into a per-tenant **Alert Rules engine** that drives the wallboard, multi-channel delivery (email / SMS / WhatsApp / webhook), and escalation chains, all running on a real worker. For the contact-center KPIs these alerts fire on, see [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md) and [13-Call-Center-KPI-and-Metrics-Reference.md](13-Call-Center-KPI-and-Metrics-Reference.md); for the target architecture this plugs into, see [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md).

## TL;DR / Key Takeaways

- **The wallboard's core KPIs are wrong.** `realtime/snapshot.py:30-31` counts answered/missed with `Q(reason_terminated='NoAnswer')`. That literal matches **0 of 1,492,192 rows** (verified) — so every wallboard shows **missed = 0** and **answer_rate = 100%** forever. This is the same data-quality disease documented in [05](05-Call-Center-Evaluation-Module.md): use `time_answered IS NULL` instead (461,602 calls / 30.9% are genuinely unanswered).
- **Nothing scheduled or retried actually runs.** Production has only `gunicorn`, `daphne`, and `socket_server` under systemd, and no app cron. Webhook retries (`api/services/webhooks.py:90-93` schedules `next_retry_at`) and the `check_quotas` management command have **no process that ever executes them**. WebhookDelivery rows pending retry would sit forever. There are **0 WebhookDeliveries** and **0 active subscriptions** today — the API is wired but unused.
- **Three signal handlers run synchronously inside the single-threaded socket ingest thread** on every CDR: realtime wallboard publish (`realtime/signals.py`), fraud evaluation (`billing/signals.py`), and webhook fan-out + blocking HTTP POST (`api/signals.py` → `api/services/webhooks.py:69`, 8s timeout). One slow webhook endpoint stalls CDR ingestion for the whole tenant.
- **Alert recipients misdeliver.** `cdr3cx/models.py:371`, `quota_views.py:193`, `views.py:960`, and `check_quotas.py:39` all **hardcode `khuram2025@gmail.com`** (a developer address). The correct line, `self.extension.user.email`, is sitting commented out at `models.py:370`. All email is sent via one global Zoho account (`no-reply@channab.com`), ignoring per-tenant `accounts.SmtpSettings`.
- **There is no alert *rules* engine and no escalation.** Notifications are a thin CRUD model (`notifications/models.py`: `recipient`, `subject`, `message`, `sent_at`) whose `post_save` blindly re-sends email. There are no thresholds, no severities, no SMS/WhatsApp channels, no escalation chains, and no de-duplication.
- **Target:** a single `EventBus` fed by ingestion → a per-tenant/per-queue `ThresholdPolicy` + `AlertRule` engine (shared with wallboard tile colouring) → a `DeliveryChannel` abstraction (email/SMS/WhatsApp/webhook) with retry, escalation, and idempotency — executed on a **Celery + Redis** worker fleet that the platform does not yet run.

---

## 1. Current state: what exists and what is broken

### 1.1 The Channels wallboard (`realtime` app)

The `realtime` app is the most modern piece of plumbing in the codebase and is genuinely well-structured. A per-company WebSocket group, an initial snapshot on connect, and a `post_save`-driven push pipeline are all present:

| Component | File | What it does | Status |
|---|---|---|---|
| `WallboardConsumer` | `realtime/consumers.py:17` | Auth-gated ASGI consumer; joins group `wallboard.company.<id>`; sends snapshot on connect; handles `refresh` | Works; tenant-scoped by `user.company.pk` |
| Event publisher | `realtime/signals.py:26-51` | `post_save` on `CallRecord` → `call.completed`; on `FraudIncident` → `fraud.detected` | Fires, but **synchronous in ingest thread** |
| Snapshot builder | `realtime/snapshot.py:16` | 24h counters, in-progress, recent ticker, hourly histogram, 7×24 heatmap | **KPI logic broken (see below)** |
| WS routing | `realtime/routing.py:7` | `ws/wallboard/` → consumer | Works (daphne :8002 per [02](02-Current-System-Architecture-Audit.md)) |
| HTML views | `realtime/views.py` | `wallboard`, `wallboard_projection` (TV mode), `heatmap` | Render server-side snapshot |

The architecture is sound: Channels + `channels_redis.core.RedisChannelLayer` (`settings.py:81-86`) over daphne is exactly the right transport for a live wallboard. The problems are in the *data*, the *runtime placement*, and the *absence of any rules layer*.

**Critical bug — the wallboard's headline numbers are fabricated.** `realtime/snapshot.py:28-35`:

```python
counts = qs.aggregate(
    total=Count('id'),
    answered=Count('id', filter=~Q(reason_terminated='NoAnswer') & ~Q(duration=None)),
    missed=Count('id', filter=Q(reason_terminated='NoAnswer')),
    ...
)
```

`reason_terminated` never contains the literal `NoAnswer`. Verified against the live DB:

```text
SELECT count(*) FROM cdr3cx_callrecord WHERE reason_terminated='NoAnswer';  ->  0
```

The real top values are `src_participant_terminated` (494,775), `TerminatedBySrc` (301,009), `dst_participant_terminated` (216,793), `Failed` (161,079), etc. — and they are themselves mixed-case duplicates ([04](04-Data-Model-and-Database-Performance.md), [13](13-Call-Center-KPI-and-Metrics-Reference.md)). Consequently the wallboard's **`missed` tile is always 0**, **`answered` ≈ total**, and **`answer_rate` ≈ 100%**. The supervisor sees a green board while a third of calls go unanswered. The fix is the same as elsewhere in the platform — use the reliable signal `time_answered IS NULL`:

```python
answered=Count('id', filter=Q(time_answered__isnull=False)),
missed=Count('id', filter=Q(time_answered__isnull=True)),
```

**Performance bug — the snapshot iterates rows in Python.** `snapshot.py:60-63` and `89-94` build the hourly histogram and 7×24 heatmap by `.iterator()`-looping every row in the window and bucketing in Python. With no index on `call_time` ([04](04-Data-Model-and-Database-Performance.md)) this is a sequential scan of up to ~3,800 calls/day pulled into the app per connect *and* on every `refresh`. Replace with a single set-based `TruncHour`/`TruncDate` + `GROUP BY` aggregate.

**Runtime bug — the wallboard cannot show true real-time queue state.** The CDR is written only at *call end*. The wallboard therefore can never display **calls-waiting-now**, **longest/oldest wait**, or **live agent states** — the metrics supervisors actually act on ([13](13-Call-Center-KPI-and-Metrics-Reference.md)). `snapshot.py:41-45` fakes "in progress" as "rows from the last 10 minutes with `time_end` NULL", which is a poor proxy. True live state must come from the 3CX Call Control API / queue feed pushed onto the same Channels group, not mined from the CDR table ([03](03-CDR-Ingestion-and-3CX-Integration.md), [05](05-Call-Center-Evaluation-Module.md)).

### 1.2 The notifications app

`notifications` is CRUD-over-email with no rules:

```python
# notifications/models.py
class Notification(models.Model):
    recipient = models.EmailField()
    subject   = models.CharField(max_length=255)
    message   = models.TextField()
    sent_at   = models.DateTimeField(default=timezone.now)
```

`notifications/signals.py:6-12` fires `send_mail` synchronously on every `Notification` save, `fail_silently=False`. There is **no notion of a trigger, threshold, severity, channel, dedup window, read/ack state, or recipient routing** — it is a sent-email log, not a notification system. The `notifications/management/commands/` directory is **empty** (no scheduled producer).

### 1.3 Quota & fraud alert paths (the only alerts that "fire")

Two real alert producers exist, both with the same defects:

- **Quota alerts** — `cdr3cx/models.py:360` `UserQuota.send_quota_alert()` runs inside `CallRecord.save()` (i.e. inside the socket thread). It `send_mail`s *and* creates a `Notification` (which triggers a *second* synchronous email via the signal above). Recipient is hardcoded:

  ```python
  # cdr3cx/models.py:370-371
  # recipient = self.extension.user.email
  recipient = 'khuram2025@gmail.com'  # developer address
  ```

  The same hardcode repeats in `quota_views.py:193`, `cdr3cx/views.py:960`, and `management/commands/check_quotas.py:39`. **Every quota alert across both tenants (Smasco, SAMNAN) goes to one developer inbox.** `check_quotas.py` is a batch sweep that is never scheduled — there is no cron, so it never runs.

- **Fraud incidents** — `billing/signals.py:16` evaluates fraud synchronously on every CDR (18,361 incidents to date). Each incident triggers a `fraud.detected` wallboard toast (`realtime/signals.py:43`) and a `fraud.detected` webhook (`api/signals.py:27`). There is **no email/SMS to a fraud owner** at all — fraud is visible only to a browser that happens to have the wallboard open.

### 1.4 The public API and webhooks (`api` app)

The webhook subsystem is the best-designed delivery code in the repo and is the right *skeleton* for the target system — but it runs in the wrong place and is essentially unused:

- `WebhookSubscription` declares 11 event types (`api/models.py:104-116`) including `call.completed`, `quota.exceeded`, `fraud.detected`, `extension.disabled`, `invoice.*`.
- `WebhookDelivery` (`api/models.py:145`) has a real delivery state machine: `status`, `attempts`, `next_retry_at`, `consecutive_failures`, plus a `(status, next_retry_at)` index built for a retry sweeper.
- `api/services/webhooks.py` does HMAC-SHA256 signing (`sign()`), fan-out, exponential backoff (`RETRY_BACKOFF_SECONDS = [0, 60, 600, 3600]`), and `MAX_ATTEMPTS = 4`.

**What's wrong:**

| Issue | Evidence | Severity / Effort |
|---|---|---|
| Delivery is **synchronous in the request/ingest thread** with an 8s HTTP timeout | `webhooks.py:69` `requests.post(..., timeout=8)`, called from `emit()` in the `CallRecord` `post_save` | **Critical** / M |
| **Retries never happen.** Backoff sets `next_retry_at` but no worker re-runs `deliver_now()` on pending rows | `webhooks.py:90-93`; no Celery/cron (verified) | **Critical** / M |
| Module docstring admits it: "*Synchronous delivery for now … wraps cleanly into a Celery task*" | `webhooks.py:3-5` | — |
| API barely adopted | **1 ApiKey, 0 subscriptions, 0 deliveries** (verified) | Low (opportunity) |

Because three independent `post_save` receivers (`realtime`, `billing`, `api`) all fire on `CallRecord` creation *inside the single-threaded socket server* ([02](02-Current-System-Architecture-Audit.md), [03](03-CDR-Ingestion-and-3CX-Integration.md)), a single unreachable webhook URL blocks CDR ingestion for up to 8 seconds **per call** for that tenant. At 3,800 calls/day this is a latent outage waiting for the first subscriber.

---

## 2. Why "scheduled" and "async" features do not fire

This is the single most important operational finding for this document. The codebase is written *as if* a worker exists — docstrings across `webhooks.py:3`, `billing/signals.py:3`, and the `check_quotas` command all reference Celery — but **no asynchronous runtime is deployed**.

| Capability | How it's coded | Why it never runs |
|---|---|---|
| Webhook retries / dead-letter | `WebhookDelivery.next_retry_at`, `status='pending'` | No process polls `WHERE status='pending' AND next_retry_at<=now()` |
| Scheduled quota check | `management/commands/check_quotas.py` | No cron / systemd timer invokes it |
| Scheduled reports ([07](07-Reporting-Dashboards-and-UI-UX.md)) | n/a (not built) | No scheduler to build on |
| Any "async" comment in signals | "*swap for `evaluate_call.delay(...)`*" | No broker, no worker |

**Verification:** systemd runs only `gunicorn.service`, `daphne.service`, `socket_server.service`; `/etc/cron.d` contains no app jobs ([02](02-Current-System-Architecture-Audit.md)). There is a Redis instance (used as the Channels layer + cache), so **the broker for Celery/RQ already exists** — only the worker and beat scheduler are missing.

**Net effect:** every alerting promise in the product is either (a) synchronous and blocking the ingest path, or (b) defined but never executed. Before promising the stakeholder "rich alerts/emails", the runtime must be fixed first.

---

## 3. Target architecture: event-driven alerting

The design separates three concerns the current code conflates: **detecting** a condition, **deciding** whether it breaches a rule, and **delivering** + **escalating** the notification — all off the ingest thread.

```text
                          ┌─────────────────────────────────────────────┐
   3CX socket / DB pull   │                 INGEST                       │
   3CX Call Control WS ──▶│  normalize → upsert CallRecord (bulk, fast)  │
   (future: CUCM, etc.)   │  emit DomainEvent ──▶ Redis Streams / Celery │
                          └───────────────────────┬─────────────────────┘
                                                   │ (events, not blocking)
        ┌──────────────────────────────────────────┼───────────────────────────┐
        ▼                                           ▼                           ▼
┌───────────────┐                       ┌────────────────────────┐   ┌────────────────────┐
│ Live wallboard│  ◀── same threshold ──│   ALERT RULES ENGINE   │──▶│ DELIVERY + ESCALATE│
│ (Channels grp)│       colours         │ ThresholdPolicy/AlertRule│   │ email/SMS/WA/webhook│
│ tiles G/A/R   │                       │ per-tenant, per-queue  │   │ retry, dedup, ack  │
└───────────────┘                       └────────────────────────┘   └────────────────────┘
```

Key principle from contact-center wallboard best practice ([13](13-Call-Center-KPI-and-Metrics-Reference.md)): **the same `ThresholdPolicy` that colours a wallboard tile amber/red also fires the alert.** One configuration, two consumers — never two divergent definitions of "breached".

### 3.1 Ingestion emits events

The ingest pipeline ([03](03-CDR-Ingestion-and-3CX-Integration.md)) should do the *minimum* synchronously (normalize + upsert) and then publish a lightweight event. Redis Streams (already have Redis) or Celery tasks both work:

```python
# After a CallRecord is committed (NOT in a post_save inside the socket thread):
events.publish(EventType.CALL_COMPLETED, company_id=rec.company_id, call_id=rec.id, payload={...})
```

This removes the three blocking `post_save` handlers from the ingest path. Fraud evaluation, wallboard push, and webhook fan-out all become **event subscribers running on the worker**.

### 3.2 The Alert Rules engine

A per-tenant, per-queue rule store that both the engine and the wallboard read:

```python
class ThresholdPolicy(models.Model):
    company        = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    queue          = models.ForeignKey('callcenter.Queue', null=True, on_delete=models.CASCADE)  # null = tenant default
    sla_target_sec        = models.PositiveIntegerField(default=20)    # 80/20 service level
    short_abandon_sec     = models.PositiveIntegerField(default=10)
    sl_amber_pct          = models.DecimalField(max_digits=5, decimal_places=2, default=85)  # warn
    sl_red_pct            = models.DecimalField(max_digits=5, decimal_places=2, default=80)  # breach
    abandon_amber_pct     = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    abandon_red_pct       = models.DecimalField(max_digits=5, decimal_places=2, default=8)
    longest_wait_red_sec  = models.PositiveIntegerField(default=180)
    quota_warn_pct        = models.PositiveIntegerField(default=90)

class AlertRule(models.Model):
    METRIC = [('service_level','SL'), ('abandon_rate','Abandon'), ('longest_wait','Longest wait'),
              ('quota_pct','Quota %'), ('fraud_incident','Fraud'), ('cost_spike','Cost spike')]
    OP     = [('lt','<'), ('gt','>'), ('gte','>='), ('lte','<=')]
    company      = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    queue        = models.ForeignKey('callcenter.Queue', null=True, on_delete=models.CASCADE)
    metric       = models.CharField(max_length=32, choices=METRIC)
    operator     = models.CharField(max_length=4, choices=OP)
    threshold    = models.DecimalField(max_digits=10, decimal_places=2)
    window_min   = models.PositiveIntegerField(default=15)   # evaluation window
    severity     = models.CharField(max_length=12, default='warning')  # info/warning/critical
    cooldown_min = models.PositiveIntegerField(default=10)   # de-duplication / anti-storm
    escalation   = models.ForeignKey('EscalationChain', null=True, on_delete=models.SET_NULL)
    is_active    = models.BooleanField(default=True)
```

**Two evaluation modes**, matching the two data paths ([05](05-Call-Center-Evaluation-Module.md)):

1. **Event-driven (instant):** single-call conditions — `quota.exceeded`, `fraud.detected`, `extension.disabled`, `cost_spike` — evaluated the moment the event arrives. Replaces the current synchronous fraud/quota emails.
2. **Window-rollup (periodic):** rate metrics — service level, abandonment %, longest wait — need a denominator over a window. A Celery-beat task every 1–5 min computes per-queue rollups (one indexed `GROUP BY`, not per-row Python) and evaluates `AlertRule`s. The same rollup feeds the wallboard tile colours.

`cooldown_min` prevents alert storms (don't re-page on the same breach every minute). Each fired alert writes an `AlertEvent` row (idempotency key = `rule_id + window_bucket`) so re-evaluation is safe.

### 3.3 Escalation chains

```python
class EscalationChain(models.Model):
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    name    = models.CharField(max_length=128)

class EscalationStep(models.Model):
    chain       = models.ForeignKey(EscalationChain, related_name='steps', on_delete=models.CASCADE)
    order       = models.PositiveSmallIntegerField()
    after_min   = models.PositiveIntegerField(default=0)   # delay before this step
    target_type = models.CharField(max_length=16)          # agent|supervisor|role|user|webhook
    target_ref  = models.CharField(max_length=128)         # resolves to recipients (NOT hardcoded)
    channels    = models.JSONField(default=list)           # ['email','sms','whatsapp']
```

Example: an SL-red breach on the **3CX San Francisco** call-center queue → step 0 notifies the on-shift supervisor (email + SMS); if unacknowledged after 5 min → step 1 notifies the contact-center manager (WhatsApp); after 15 min → step 2 posts to an ops webhook. Recipients are **resolved**, never hardcoded — directly fixing the `khuram2025@gmail.com` defect.

---

## 4. Delivery channels and reliability

### 4.1 Channel abstraction

Replace the single global `send_mail` with a `DeliveryChannel` interface so the same alert can fan to multiple media:

```python
class DeliveryChannel(ABC):
    code: str  # 'email' | 'sms' | 'whatsapp' | 'webhook'
    @abstractmethod
    def send(self, recipient, subject, body, *, context) -> DeliveryResult: ...
```

| Channel | Recommended provider | Notes |
|---|---|---|
| **Email** | Per-tenant `accounts.SmtpSettings` (already modelled) with global Zoho fallback | Stop forcing all mail through `no-reply@channab.com` (`settings.py:139-142`). Render via existing `notifications/quota_alert_email.html` templates. |
| **SMS** | Twilio / Unifonic (Unifonic is KSA-native; `TIME_ZONE=Asia/Riyadh`) | Short, link to dashboard. Good for SL/abandon breaches. |
| **WhatsApp** | Twilio WhatsApp or Meta Cloud API (template messages) | Highest-engagement for supervisor escalations in MENA. |
| **Webhook** | Reuse `api/services/webhooks.py` | Make it an alert channel, not just a CDR mirror. |

### 4.2 Delivery reliability — generalise the webhook state machine

The `WebhookDelivery` model already encodes the right pattern (`attempts`, `next_retry_at`, backoff, dead-letter). Promote it to a generic `OutboundDelivery` covering all channels, and **add the worker that the design assumed all along**:

```python
@shared_task(bind=True, max_retries=4)
def process_pending_deliveries(self):
    due = OutboundDelivery.objects.filter(status='pending', next_retry_at__lte=now())
    for d in due.iterator():
        deliver_now(d)          # existing logic, now off the request thread
```

```python
# celery beat schedule
beat_schedule = {
  'webhook-retry-sweep':  {'task': 'deliveries.process_pending', 'schedule': 30.0},
  'kpi-rollup-and-alert': {'task': 'alerts.evaluate_windowed',   'schedule': 60.0},
  'quota-sweep':          {'task': 'quota.check_all',            'schedule': 300.0},
}
```

Reliability requirements: at-least-once delivery with idempotency keys; per-recipient rate limiting (don't SMS-bomb a supervisor); a dead-letter queue (`status='giving_up'`, already in `api/models.py:152`) surfaced in an admin dashboard; and a `last_success_at`/`consecutive_failures` health view (already on `WebhookSubscription`) to auto-disable chronically failing endpoints.

---

## 5. Making the public API & webhooks useful

The API is fully built (DRF + drf-spectacular + `ApiKey` tiers + HMAC webhooks) but has **1 key, 0 subscriptions, 0 deliveries**. To convert plumbing into value:

1. **Move delivery to the worker** (Section 4.2) so subscribers can't stall ingestion and retries actually happen.
2. **Wire the declared events that have no producer.** `quota.threshold`, `quota.exceeded`, `extension.disabled`, and `invoice.*` are in `EVENT_CHOICES` (`api/models.py:104-116`) but nothing emits them. Hook them to the new `EventBus` alongside the existing `call.completed`/`fraud.detected`.
3. **Use webhooks as a first-class alert channel**, so a tenant can route SL/fraud/quota alerts into Slack/Teams/their CRM ([10](10-Multi-Vendor-and-Target-Architecture.md)).
4. **Document and seed** the API for the priority SF tenant and Power BI users (per the strategy docs); the schema already supports per-tenant scoping and read tiers.

---

## 6. Worker deployment recommendation

The platform already runs Redis. Add a worker tier — minimal new infrastructure:

| Option | Fit | Recommendation |
|---|---|---|
| **Celery + Redis broker + Celery Beat** | Mature, supports scheduled (beat) + async tasks, retries, dead-letter, monitoring (Flower) | **Recommended.** Reuse existing Redis (separate DB index from Channels). |
| RQ + rq-scheduler | Simpler, lighter | Viable for a smaller footprint, weaker scheduling/monitoring. |
| systemd timers only | No queue semantics | Insufficient — no retries/fan-out. |

Deploy as **two systemd units** alongside `gunicorn`/`daphne`/`socket_server` ([02](02-Current-System-Architecture-Audit.md)):

```ini
# celery-worker.service  → celery -A cdr worker -Q alerts,deliveries,ingest --concurrency=4
# celery-beat.service    → celery -A cdr beat
```

Settings already note signal handlers "may run in any worker / Celery" (`settings.py:79`), so the codebase anticipates this. Concretely:

- **Workers** consume the `EventBus` (fraud eval, wallboard push, webhook/alert fan-out — all the work currently blocking the socket thread).
- **Beat** runs the windowed KPI rollups, retry sweep, and quota sweep that have no runtime today.
- Use a **dedicated Redis DB index** for Celery so it doesn't contend with the Channels layer; size concurrency to current load (~2k–3.8k calls/day is light).

---

## 7. Findings & recommendations summary

| # | Finding (current) | Recommendation (target) | Severity | Effort |
|---|---|---|---|---|
| 1 | Wallboard answered/missed use `reason_terminated='NoAnswer'` → 0 rows; missed always 0, answer_rate ~100% (`snapshot.py:30-31`) | Use `time_answered IS NULL`; align with [13](13-Call-Center-KPI-and-Metrics-Reference.md) | **Critical** | S |
| 2 | Webhook retries & `check_quotas` never execute (no worker/cron) | Deploy Celery worker + Beat (Redis already present) | **Critical** | M |
| 3 | Webhook/fraud/quota work runs synchronously in the single-threaded socket ingest path | Emit events; subscribers run on worker | **Critical** | M |
| 4 | Quota alert recipient hardcoded `khuram2025@gmail.com` in 4 places; correct line commented at `models.py:370` | Resolve via `EscalationStep`/`extension.user.email`; per-tenant SMTP | **High** | S |
| 5 | No alert *rules* engine — no thresholds, severity, dedup, escalation | `ThresholdPolicy` + `AlertRule` + `EscalationChain`, shared with wallboard | **High** | L |
| 6 | Fraud incidents (18,361) notify only an open browser; no email/SMS owner | Route `fraud.detected` through delivery + escalation | **High** | M |
| 7 | Only email exists; no SMS/WhatsApp | `DeliveryChannel` abstraction (email/SMS/WhatsApp/webhook) | **High** | M |
| 8 | Wallboard can't show live calls-waiting/longest-wait/agent state (CDR is end-of-call only) | Feed Channels group from Call Control/queue API ([03](03-CDR-Ingestion-and-3CX-Integration.md), [05](05-Call-Center-Evaluation-Module.md)) | Medium | L |
| 9 | Snapshot loops rows in Python; no `call_time` index | Set-based `GROUP BY` + composite index ([04](04-Data-Model-and-Database-Performance.md)) | Medium | S |
| 10 | API fully built but unused (1 key, 0 subs, 0 deliveries); 4 declared events have no producer | Wire events to `EventBus`; webhooks as alert channel | Medium | M |

### Phased delivery (aligns with [12](12-Migration-Plan-and-Phased-Roadmap.md))

- **Phase 0 (days):** Fix #1 and #4 — correct the wallboard KPI filter and the hardcoded recipient. Two small, high-impact edits.
- **Phase 1 (weeks):** Stand up Celery + Beat (#2, #3); move webhook delivery and fraud/quota notification off the ingest thread; add the retry sweep.
- **Phase 2:** Build `ThresholdPolicy`/`AlertRule`/`EscalationChain` (#5, #6) and SMS/WhatsApp channels (#7); share thresholds with wallboard tile colouring.
- **Phase 3:** Live supervisor wallboard from the Call Control feed (#8); activate the API/webhook ecosystem (#10) for the SF call-center tenant.

The end state is one coherent loop: **ingestion emits → rules engine evaluates against per-tenant thresholds → the same thresholds colour the wallboard and fire tiered, multi-channel, escalating alerts that reach the right person** — all on a worker the platform finally runs. See [05](05-Call-Center-Evaluation-Module.md) for the metrics, [06](06-Billing-Quota-and-Fraud.md) for quota/fraud rules, and [10](10-Multi-Vendor-and-Target-Architecture.md) for how this event bus generalises across vendors.
