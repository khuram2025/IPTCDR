# Gap Analysis & Prioritized Backlog

This document consolidates every audit, research stream, and prior-work reconciliation across the connect.zentryc.com 3CX platform into a single master gap matrix and a deduplicated, prioritized backlog. It is the canonical source-of-truth that feeds the phased roadmap in [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md); the domain documents ([02](02-Current-System-Architecture-Audit.md)–[10](10-Multi-Vendor-and-Target-Architecture.md), [13](13-Call-Center-KPI-and-Metrics-Reference.md)) hold the detail, and this document indexes them rather than restating them. Every finding below is paired with a recommendation and tagged with severity and effort so engineering and stakeholders can triage from one table.

## TL;DR / Key Takeaways

- **A handful of small, cheap fixes unlock disproportionate value.** The flagship call-center bug (`Q(to_type='Ivr')` exact-case filter at `cdr3cx/callcenter_views.py:52,68`) and the broken `reason_terminated='NoAnswer'` filter (`:57,105`) silently drop roughly **half** of all call-center records — they match `Ivr`(112,642) but not `ivr`(136,928), and `NoAnswer` matches **zero** of 1,492,192 rows. Both are **S**-effort fixes that resolve the open "call Statics not showing data" complaint.
- **There is no index on `call_time`** (verified: `cdr3cx_callrecord` has indexes only on `company_id`, `source_pbx`, `external_id`, `correlation_id`). Every dashboard and report sequentially scans 1.49M rows. One **S** migration removes the platform's single largest systemic performance liability.
- **Nothing asynchronous actually runs in production** — there is no Celery and no app cron (systemd has only gunicorn/daphne/socket_server). Every "scheduled report" and "async alert" feature is effectively dead, and `UserQuota.send_quota_alert()` hardcodes `recipient='khuram2025@gmail.com'` (`cdr3cx/models.py:371`), so all quota alerts misdeliver to a developer.
- **The production environment is unhardened**: `DEBUG=True` (`cdr/settings.py:25`), `ALLOWED_HOSTS=['*']`, a committed `django-insecure-...` `SECRET_KEY` (`:22`), DB credentials in source, and an **auth-less public socket** on port 8000 already being probed by `androxgh0st` scanners (`cdr3cx/records.txt`).
- **The richest call-center data does not exist in our schema at all.** There are no Queue, Agent, AgentState, Disposition, Recording, or CallLeg models, and `CallRecord` lacks direction, ring/wait/hold/wrap time, and an abandoned flag — so Service Level, ASA, Occupancy, Adherence, and FCR are uncomputable until a new ACD model layer is added.
- **The backlog below organizes ~40 stories into 11 epics tagged P0–P3.** P0 is "fix what is broken and dangerous in days"; P1 is "make the call-center module credible"; P2–P3 are the vendor-neutral, multi-vendor, AI-grade build-out.

---

## 1. Top 10 Critical Fixes

These are the highest impact-to-effort items in the entire portfolio. Each is small enough to land inside the first one or two sprints and each removes either a correctness defect, a security exposure, or a systemic performance cliff. Severity is the blast radius if unaddressed; effort uses S/M/L/XL (S ≈ <1 day, M ≈ days, L ≈ 1–2 weeks, XL ≈ a month+).

| # | Fix | Evidence (path:line / data) | Severity | Effort | Impact |
|---|-----|------------------------------|----------|--------|--------|
| 1 | **Case-normalize call-center type filters.** Replace `Q(to_type='Ivr')` / `final_type='Extension'` with case-insensitive / canonical matching. | `callcenter_views.py:52,68,104-107,230,289,361,401`; DB: `Ivr`=112,642 vs `ivr`=136,928, `Extension`=84,297 vs `extension`=67,967 | Critical | S | Recovers ~half of all call-center records; closes the open `issues.txt` complaint |
| 2 | **Fix the missed-call predicate.** `reason_terminated='NoAnswer'` matches **0** rows; use `time_answered IS NULL` instead. | `callcenter_views.py:57,105,158,291,363,403`; DB: literal `NoAnswer` absent, 461,602/1,492,192 (30.9%) have `time_answered IS NULL` | Critical | S | Makes "missed", abandonment, and answered% correct for the first time |
| 3 | **Add `(company_id, call_time)` index.** No `call_time` index exists today. | `pg_indexes` shows only `company_id`/`source_pbx`/`external_id`/`correlation_id`; every report filters `call_time` over 1.49M rows | High | S | Eliminates sequential scans across all dashboards/reports |
| 4 | **Fix `recv(1024)` truncation.** Loop `recv` until the connection closes instead of one hard 1024-byte read. | `socket_server.py:31` (`request = client_socket.recv(1024)`) | High | S | Stops silent truncation/corruption of long records (display names) |
| 5 | **Fix hardcoded alert recipient.** `send_quota_alert()` always emails `khuram2025@gmail.com`. | `models.py:371` | High | S | Quota/escalation alerts reach the actual tenant/extension owner |
| 6 | **Turn off `DEBUG` and lock `ALLOWED_HOSTS`/`SECRET_KEY`.** | `settings.py:22,25,27` | Critical | S | Removes prod stack-trace/secret leakage; see [09](09-Security-and-Compliance.md) |
| 7 | **Move secrets out of source** (DB creds, `SECRET_KEY`) to env/secret store. | `settings.py:22` + `read/Read@123` in source | Critical | S | Stops credential exposure in VCS |
| 8 | **Allowlist the CDR socket to the known PBX IP(s).** Port 8000 is public and auth-less. | `records.txt` (androxgh0st probes); socket has no auth | High | S | Closes an internet-exposed ingestion endpoint; see [03](03-CDR-Ingestion-and-3CX-Integration.md) |
| 9 | **Add `select_for_update()` to quota deduction.** Quota mutation in `CallRecord.save()` has no row lock. | `models.py:194-249` (`save()` → `update_user_quota()`), no `select_for_update` | High | S | Removes balance race under concurrent inserts; see [06](06-Billing-Quota-and-Fraud.md) |
| 10 | **Bound the `apply_pattern_to_call_records` re-save.** A `post_save` on `CallPattern` re-saves *all* matching historical records synchronously. | `models.py:57-58` (`@receiver(post_save, sender=CallPattern)`) | High | M | Stops an unbounded synchronous reprocess that can stall ingestion |

**Why these first:** items 1, 2, 4, and 10 are correctness/ingestion defects that corrupt the data every downstream feature depends on; items 3, 9 are correctness-under-load; items 6, 7, 8 are active security exposures. None requires the new model layer or a worker — they are pure debt paydown and are prerequisites for everything in §3. Items that *do* require new infrastructure (a worker, the ACD model layer) are deliberately excluded here and live in the backlog.

---

## 2. Capability Gap Matrix by Domain

Status legend: **Missing** (does not exist), **Partial** (schema/plumbing exists but not wired or only heuristic), **OK** (functional, may need polish). Detail lives in the linked domain document.

### 2.1 Ingestion — see [03](03-CDR-Ingestion-and-3CX-Integration.md)

| Capability | Status | Current state | Target |
|------------|--------|---------------|--------|
| Transport framing | Partial | One `recv(1024)` per TCP connection; truncates long records (`socket_server.py:31`) | Loop-read to connection close; length-aware framing |
| Field mapping | Partial | Positional split into 20 fields; admin reorder silently corrupts columns | Configuration- / column-name-driven mapping per tenant |
| Idempotency / dedup | Missing | No `historyid`/`callid`/GUID captured; no dedup key | Pull `cdr_id` GUID (v20 U6 `cdr_output`); `upsert` on `(source_pbx, external_id)` |
| Authentication | Missing | Public auth-less socket on :8000 (`records.txt` probes) | IP allowlist now; strategic shift to outbound read-only DB pull |
| Strategic source | Missing | Only legacy socket CDR | Vendor-neutral PULL connector reading 3CX `cdr_output`+`cdr_billing` and queue/agent DB views |
| Case/enum normalization | Missing | Mixed-case tokens persisted raw (`Ivr`/`ivr`, `src_participant_terminated`/`TerminatedBySrc`) | Canonical lowercase enums at ingest, shared by socket and DB paths |
| Async enrichment | Missing | Country lookup, categorize, costing, quota all run inline in socket thread (`models.py:194-249`) | Bulk insert raw → idempotent enrichment step on a worker |

### 2.2 Data Model & DB — see [04](04-Data-Model-and-Database-Performance.md)

| Capability | Status | Current state | Target |
|------------|--------|---------------|--------|
| `call_time` indexing | Missing | No index; seq-scans on 1.49M rows | `(company_id, call_time)` composite index |
| Partitioning | Missing | Single 1.49M-row table spanning 22 months | Range-partition by month/`call_time` as volume grows |
| Direction / ring / wait / hold / wrap | Missing | `CallRecord` has none of these | Add `direction`, `ring_time`, `wait_time`, `hold_time`, `wrap_time`, `abandoned`, `disposition` |
| Queue / Agent / AgentState | Missing | No such models; agents inferred from display names | New `Queue`, `Agent`, `AgentState`, `Disposition`, `CallLeg`, `Recording` models |
| QoS columns | Partial | `mos`/`jitter_ms`/`packet_loss_pct`/`latency_ms` exist but **100% NULL** | Populate from RTCP-XR / 3CX Call Quality feed (separate workstream) |
| Vendor-neutral keys | OK | `source_pbx`, `external_id`, `correlation_id`, `raw_data(jsonb)` present | Reuse as the canonical multi-vendor foundation ([10](10-Multi-Vendor-and-Target-Architecture.md)) |

### 2.3 Call Center — see [05](05-Call-Center-Evaluation-Module.md) and [13](13-Call-Center-KPI-and-Metrics-Reference.md)

| Capability | Status | Current state | Target |
|------------|--------|---------------|--------|
| Call-center call identification | Partial | Heuristic `to_type=='Ivr'` + display-name match, exact-case (drops ~half) | Canonical normalized filter; queue membership from 3CX DB views |
| Service Level / ASA / Abandonment | Missing | Not computed | Derive from `time_answered`/`call_time`/`time_end`; per-queue SLA threshold config |
| AHT / ACW / Occupancy / Adherence | Missing | Only talk-time (`duration`) exists | Talk-time now; ACW/Occupancy/Adherence need AgentState + schedule layer |
| Agent / supervisor evaluation | Missing | No agent state, QA, or scorecards | `AgentState`, `Evaluation`/`Scorecard`/`Calibration`; monitor/whisper/barge via Call Control API |
| Dashboard query pattern | Partial | 24 per-hour + 21 daily COUNT scans; `call_back_tracking` N+1 (`callcenter_views.py`) | Single `GROUP BY date_trunc` / materialized rollups |
| Real-time wallboard | Missing | No live queue/agent state | Channels/Redis wallboard fed by live Call Control/Queue feed |
| FCR / CSAT / NPS / QA | Missing | None | Survey subsystem + repeat-contact approximation + QA scorecards |

### 2.4 Billing, Quota & Fraud — see [06](06-Billing-Quota-and-Fraud.md)

| Capability | Status | Current state | Target |
|------------|--------|---------------|--------|
| Rating | OK | CallPattern → rate_per_min (SAR), round-up | Keep; externalize from synchronous save path |
| Quota correctness | Partial | Deducted inline, no `select_for_update`; `deduct_balance()` no longer blocks on overage | Locked deduction; explicit overage policy/enforcement |
| Quota alert delivery | Missing | Hardcoded dev recipient (`models.py:371`) | Resolve to extension/tenant owner |
| Multi-currency / tax | Partial | `Currency` (13 rows), `TaxRule` modeled, not fully wired to UI | Wire into rating + invoices |
| Invoicing / payments / dunning | Missing | No invoices, payments, or gateway | Net-new billing-run + payment integration |
| Fraud | OK | `FraudRule`/`FraudIncident` live (18,361 incidents), incident dashboard | Tune rules; tie into alert engine |

### 2.5 Reporting / UI-UX — see [07](07-Reporting-Dashboards-and-UI-UX.md)

| Capability | Status | Current state | Target |
|------------|--------|---------------|--------|
| Report library | Partial | Ad-hoc reports; no formal ACD reports | 50+ prebuilt library with drill-down |
| Cradle-to-grave drill-down | Missing | No per-leg assembly | Stitch legs via `correlation_id` |
| Scheduled reports | Missing | Feature exists in intent but **no worker runs it** | Real scheduler: recurrence, window, timezone, PDF/XLSX/CSV, email+FTP |
| Dashboard UX | Partial | Static pages, full-scan queries | Widget drag-drop, light/dark, threshold-colored tiles |
| Exports / RTL | Partial | Basic; `TIME_ZONE=Asia/Riyadh` (MENA/RTL audience) | Robust exports + RTL design system |

### 2.6 Real-time & Alerts — see [08](08-Realtime-Alerts-and-Notifications.md)

| Capability | Status | Current state | Target |
|------------|--------|---------------|--------|
| Channels wallboard | Partial | `realtime` app + snapshot consumer exist | Drive from live queue/agent feed, not CDR table |
| Alert rules engine | Missing | No threshold policy; alerts misdeliver | Per-tenant/per-queue `ThresholdPolicy` driving colors + alerts + escalation |
| Worker runtime | Missing | No Celery / no cron in prod | Real worker (Celery/RQ) or on-ingest evaluation |
| Channels (email/SMS/WhatsApp) | Partial | `notifications` app + email only | Multi-channel with escalation |

### 2.7 API — see [10](10-Multi-Vendor-and-Target-Architecture.md)

| Capability | Status | Current state | Target |
|------------|--------|---------------|--------|
| REST API | OK | DRF + drf-spectacular live | Keep; broaden coverage |
| Webhooks | Partial | `WebhookSubscription`/`Delivery` modeled; **0 deliveries** | Wire delivery to a worker; sign payloads |
| Adoption | Partial | Only **1** `ApiKey` issued | Document + drive usage once worker exists |

### 2.8 Security — see [09](09-Security-and-Compliance.md)

| Capability | Status | Current state | Target |
|------------|--------|---------------|--------|
| Prod hardening | Missing | `DEBUG=True`, `ALLOWED_HOSTS=['*']`, committed `SECRET_KEY` (`settings.py:22,25,27`) | Hardened settings, secret store |
| TLS | Missing | nginx listens :80 only | Terminate TLS; HSTS |
| Tenant isolation | Partial | `company_middleware`, port-based tenant resolution | Enforce on every query; audit |
| Audit / password policy / session timeout | OK | `security` app provides these | Keep; extend retention/compliance |

---

## 3. Prioritized Backlog (Epics → Stories)

Priorities: **P0** = correctness/security/perf debt, ship in days, no new infra; **P1** = make the call-center module credible and the platform safe to scale; **P2** = vendor-neutral build-out and rich reporting/alerting; **P3** = AI-grade differentiation. Effort is S/M/L/XL per §1. Stories are deduplicated across all domain docs — where a story serves several domains it appears once with cross-links.

### Epic A — Data-Quality & Correctness (P0)
| Story | Effort | Links |
|-------|--------|-------|
| A1. Case-normalize all `*_type` and `reason_terminated` filters in call-center views | S | [05](05-Call-Center-Evaluation-Module.md) |
| A2. Replace `reason_terminated='NoAnswer'` with `time_answered IS NULL`; classify `Failed`/`no_route`/`busy`/`declined` as system-disposed vs customer-abandoned | S | [05](05-Call-Center-Evaluation-Module.md), [13](13-Call-Center-KPI-and-Metrics-Reference.md) |
| A3. Add canonical normalized columns/enums (`call_disposition`, normalized type) populated at ingest | M | [03](03-CDR-Ingestion-and-3CX-Integration.md), [04](04-Data-Model-and-Database-Performance.md) |
| A4. Backfill/normalize existing 1.49M rows (one-off migration) | M | [04](04-Data-Model-and-Database-Performance.md) |

### Epic B — Performance Foundation (P0)
| Story | Effort | Links |
|-------|--------|-------|
| B1. Add `(company_id, call_time)` index | S | [04](04-Data-Model-and-Database-Performance.md) |
| B2. Replace 24 per-hour + 21 daily COUNT scans with single grouped/aggregate queries | M | [05](05-Call-Center-Evaluation-Module.md), [07](07-Reporting-Dashboards-and-UI-UX.md) |
| B3. Eliminate `call_back_tracking` N+1 loop | S | [05](05-Call-Center-Evaluation-Module.md) |
| B4. Range-partition `cdr3cx_callrecord` by month | L | [04](04-Data-Model-and-Database-Performance.md) |

```sql
-- B1: the single highest-leverage performance change
CREATE INDEX CONCURRENTLY idx_callrecord_company_calltime
    ON cdr3cx_callrecord (company_id, call_time);
```

### Epic C — Security Hardening (P0)
| Story | Effort | Links |
|-------|--------|-------|
| C1. `DEBUG=False`, explicit `ALLOWED_HOSTS`, rotated `SECRET_KEY` from env | S | [09](09-Security-and-Compliance.md) |
| C2. Move DB creds/secrets to env/secret store | S | [09](09-Security-and-Compliance.md) |
| C3. IP-allowlist the CDR socket; plan migration off public inbound socket | S | [03](03-CDR-Ingestion-and-3CX-Integration.md) |
| C4. Terminate TLS at nginx; HSTS | M | [09](09-Security-and-Compliance.md) |

### Epic D — Ingestion Hardening (P0/P1)
| Story | Effort | Priority | Links |
|-------|--------|----------|-------|
| D1. Loop-read socket to connection close (fix `recv(1024)`) | S | P0 | [03](03-CDR-Ingestion-and-3CX-Integration.md) |
| D2. Bound/queue `apply_pattern_to_call_records` re-save off the request/socket thread | M | P0 | [03](03-CDR-Ingestion-and-3CX-Integration.md) |
| D3. Move country/categorize/costing/quota out of `save()` into idempotent enrichment | M | P1 | [03](03-CDR-Ingestion-and-3CX-Integration.md), [06](06-Billing-Quota-and-Fraud.md) |
| D4. Vendor-neutral `BaseCDRAdapter` (`fetch`/`normalize`/`correlate`/`upsert`) | L | P2 | [10](10-Multi-Vendor-and-Target-Architecture.md) |
| D5. 3CX DB pull connector (read-only `cdr_output`+`cdr_billing`, queue/agent views, version-detecting) | L | P2 | [03](03-CDR-Ingestion-and-3CX-Integration.md) |

### Epic E — Worker & Async Runtime (P1)
| Story | Effort | Links |
|-------|--------|-------|
| E1. Stand up a real worker (Celery/RQ) + beat, under systemd | M | [02](02-Current-System-Architecture-Audit.md), [08](08-Realtime-Alerts-and-Notifications.md) |
| E2. Move enrichment, scheduled reports, webhook delivery, alert evaluation onto it | M | [07](07-Reporting-Dashboards-and-UI-UX.md), [08](08-Realtime-Alerts-and-Notifications.md) |

> **Dependency note:** Epics F (scheduled reports), the alert engine in I, and webhook delivery in §2.7 are all blocked on E1 — there is no worker in production today, so they cannot ship until a runtime exists.

### Epic F — Call-Center ACD Model & Metrics (P1)
| Story | Effort | Links |
|-------|--------|-------|
| F1. Add `direction`, `ring_time`, `wait_time`, `hold_time`, `wrap_time`, `abandoned` to `CallRecord` | M | [04](04-Data-Model-and-Database-Performance.md) |
| F2. New `Queue`, `Agent`, `AgentState`, `Disposition`, `CallLeg`, `Recording` models (vendor-neutral) | L | [05](05-Call-Center-Evaluation-Module.md), [10](10-Multi-Vendor-and-Target-Architecture.md) |
| F3. Per-tenant/per-queue `ThresholdPolicy` (SLA target, short-abandon, alert thresholds) | M | [05](05-Call-Center-Evaluation-Module.md), [08](08-Realtime-Alerts-and-Notifications.md) |
| F4. Compute Service Level, ASA, Abandonment, Avg/Longest Wait, Answered% from CDR | M | [13](13-Call-Center-KPI-and-Metrics-Reference.md) |
| F5. AgentState feed (3CX Call Control WebSocket) → Occupancy, Adherence, ACW | L | [05](05-Call-Center-Evaluation-Module.md) |
| F6. Role-based dashboards (Agent / Supervisor / Manager) + live wallboard | L | [07](07-Reporting-Dashboards-and-UI-UX.md), [08](08-Realtime-Alerts-and-Notifications.md) |

```python
# F4: Service Level / ASA computable today from existing columns after A1/A2 + B1
from django.db.models import Avg, Count, Q, F, ExpressionWrapper, DurationField

wait = ExpressionWrapper(F("time_answered") - F("call_time"), output_field=DurationField())
qs = (CallRecord.objects
      .filter(company=tenant, call_time__range=(start, end))      # uses idx_callrecord_company_calltime
      .filter(direction="inbound"))                                # normalized, case-insensitive
metrics = qs.aggregate(
    answered=Count("id", filter=Q(time_answered__isnull=False)),
    within_sla=Count("id", filter=Q(time_answered__isnull=False) & Q(**{f"{wait}__lte": sla})),  # see 13
    asa=Avg(wait, filter=Q(time_answered__isnull=False)),
    abandoned=Count("id", filter=Q(time_answered__isnull=True)),
)
```

### Epic G — Billing & Quota Correctness (P1/P2)
| Story | Effort | Priority | Links |
|-------|--------|----------|-------|
| G1. `select_for_update()` on quota deduction; explicit overage enforcement | S | P1 | [06](06-Billing-Quota-and-Fraud.md) |
| G2. Fix quota alert recipient routing | S | P1 | [06](06-Billing-Quota-and-Fraud.md), [08](08-Realtime-Alerts-and-Notifications.md) |
| G3. Wire multi-currency + tax into rating | M | P2 | [06](06-Billing-Quota-and-Fraud.md) |
| G4. Invoicing / payments / dunning subsystem | XL | P2 | [06](06-Billing-Quota-and-Fraud.md) |

### Epic H — Reporting & UI/UX (P2)
| Story | Effort | Links |
|-------|--------|-------|
| H1. Scheduled-report engine (recurrence, window, timezone, PDF/XLSX/CSV, email+FTP) | L | [07](07-Reporting-Dashboards-and-UI-UX.md) |
| H2. Prebuilt report library (target 50+) + cradle-to-grave drill-down via `correlation_id` | L | [07](07-Reporting-Dashboards-and-UI-UX.md) |
| H3. Widget drag-drop dashboards, light/dark, RTL design system | L | [07](07-Reporting-Dashboards-and-UI-UX.md) |

### Epic I — Alerts & Notifications (P2)
| Story | Effort | Links |
|-------|--------|-------|
| I1. Threshold alert engine driven by the same `ThresholdPolicy` as wallboard colors (F3) | M | [08](08-Realtime-Alerts-and-Notifications.md) |
| I2. Multi-channel delivery (email/SMS/WhatsApp) + tiered escalation to supervisor | L | [08](08-Realtime-Alerts-and-Notifications.md) |
| I3. Wire webhook deliveries onto the worker; sign payloads | M | [10](10-Multi-Vendor-and-Target-Architecture.md), [08](08-Realtime-Alerts-and-Notifications.md) |

### Epic J — Multi-Vendor Expansion (P2/P3)
| Story | Effort | Priority | Links |
|-------|--------|----------|-------|
| J1. Cisco CUCM adapter (SFTP CDR+CMR flat-file poller; CMR → QoS columns) | L | P2 | [10](10-Multi-Vendor-and-Target-Architecture.md) |
| J2. Teams / Webex / Zoom REST poller adapters | L | P3 | [10](10-Multi-Vendor-and-Target-Architecture.md) |
| J3. `ingest_transport` lineage tag + version/edition detection per tenant | M | P2 | [03](03-CDR-Ingestion-and-3CX-Integration.md) |

### Epic K — Intelligence & QA (P3)
| Story | Effort | Links |
|-------|--------|-------|
| K1. QA Scorecard/Evaluation/Calibration models + recordings linkage | L | [05](05-Call-Center-Evaluation-Module.md) |
| K2. Post-call survey subsystem (CSAT/NPS/CES) + FCR repeat-contact approximation | L | [13](13-Call-Center-KPI-and-Metrics-Reference.md) |
| K3. QoS/MOS ingestion (RTCP-XR / 3CX Call Quality) to populate the empty QoS columns | L | [04](04-Data-Model-and-Database-Performance.md) |
| K4. AI layer: transcription, sentiment, anomaly callouts | XL | [10](10-Multi-Vendor-and-Target-Architecture.md) |

---

## 4. Relationship to Prior Work and the Roadmap

The earlier business-strategy set under `/home/ubuntu/3CX/enhancement/` (the "IPT Bill / IPT Insight / IPT Contact" product lines, pricing, and 18-month MENA roadmap, authored 2026-05-12) remains useful for market positioning but is **superseded for engineering purposes** by this documentation set. Notably, much of the recent git work (vendor-neutral CDR fields, multi-currency/tax/fraud models, REST API + webhooks, Channels wallboard, security baseline) is **schema/plumbing only** — the gap matrix above repeatedly marks these "Partial" precisely because they are modeled but not wired into operations (e.g., webhooks have 0 deliveries, the QoS columns are 100% NULL, scheduled reports have no worker). The value now is in *activating* that plumbing, not re-building it.

The **priority sequencing** for the stakeholder's named goals maps onto the epics as follows, and is expanded with milestones, risks, and rollback in [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md):

1. **Stop the bleeding (P0):** Epics A, B, C, D1/D2 — days of work that fix the silent data loss, the missing index, and the live security exposures.
2. **Make the 3CX San Francisco call-center tenant credible (P1):** Epics E and F — a worker plus the ACD model layer and corrected Service Level / ASA / Abandonment / wallboard.
3. **Vendor-neutral, rich-reporting platform (P2):** Epics D4/D5, G, H, I, J1 — the pull connector, real reporting/alerting, and the first non-3CX (Cisco CUCM) adapter.
4. **Differentiated intelligence (P3):** Epics J2 and K — additional cloud vendors, QA/survey/QoS, and the AI layer.

This document should be re-baselined whenever an epic completes so the matrix reflects "OK" status and the backlog stays the single source of truth feeding the roadmap.
