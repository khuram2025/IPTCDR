# Migration Plan & Phased Roadmap

This document is the engineering execution plan to evolve the `connect.zentryc.com` platform from its current single-server Django monolith into a vendor-neutral, multi-tenant call-accounting and call-center-evaluation product — **without breaking the live 1.49M-row database or the two active tenants (Smasco, SAMNAN)**. It sequences the work as phases (P0–P6) with explicit goals, scope, exit criteria, risks, and rollback, and it draws its line-items from the consolidated backlog in [11-Gap-Analysis-and-Feature-Backlog.md](11-Gap-Analysis-and-Feature-Backlog.md). It supersedes, for engineering purposes, the older market-strategy roadmap at `/home/ubuntu/3CX/enhancement/` (which remains valid for pricing/go-to-market).

## TL;DR / Key Takeaways

- **P0 is non-negotiable and ships in days, not weeks.** Four production-correctness/safety fixes (the mixed-case `*_type` bug, the missing `call_time` index, the hardcoded alert recipient `khuram2025@gmail.com`, and the auth-less internet-exposed socket) are all low-effort, high-impact, and reversible. Verified live: `Ivr`(112,642) **and** `ivr`(136,928); `Extension`(84,297) **and** `extension`(67,967) — the call-center filters use exact case and silently drop ~half the data.
- **Stand up a real Celery worker + Redis broker in P0.** Production runs only `gunicorn`, `daphne`, and `socket_server` (verified via `systemctl`); there is **no** worker and **no** app cron. Every "scheduled report" / "async" / "alert" feature in the codebase is currently dead code. Nothing in P3–P6 works until a worker exists.
- **The data is the asset; protect it.** 1,492,192 CallRecords spanning 2024-07-31 → 2026-06-05, all `source_pbx=3cx`. Every phase uses an **expand → migrate → contract** schema discipline, additive backfills, and a tenant-by-tenant rollout (Smasco/SAMNAN never both at risk simultaneously).
- **Call-center evaluation (P2) is the priority deliverable** for the 3CX San Francisco pilot tenant — see [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md). It depends on the ingestion/data foundation in P1.
- **Multi-vendor (Cisco CUCM) and AI/QA are deliberately late (P5/P6).** They are valuable but depend on the canonical schema and adapter pattern landed in P1 — see [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md).
- **Migration-safety stance:** read-only-first, additive-only DDL, dual-write/dual-read during cutovers, online (`CONCURRENTLY`) index builds, and a documented rollback per phase. No phase requires downtime for the live tenants.

---

## 1. Migration Principles (the safety contract)

Every phase below obeys these rules. They exist because the live database carries 22 months of billing-relevant history for paying tenants and a corrupt or downed CDR pipeline means lost, unre-creatable call records.

| Principle | What it means in practice |
| --- | --- |
| **Read-only first** | New ingestion (DB-pull connector, P1) is built and validated as a *shadow* path writing to a staging area before it ever replaces the socket feed. The existing `socket_server.service` keeps running untouched until shadow reconciliation matches. |
| **Additive-only DDL** | New columns are `NULL`-able / defaulted; indexes are built `CREATE INDEX CONCURRENTLY` (no table lock on 1.49M rows). No destructive `ALTER`/`DROP` until an **expand → migrate → contract** cycle has fully completed and been observed in production for ≥1 release. |
| **Idempotent, resumable backfills** | Historical normalization (mixed-case fix, derived columns) runs in bounded batches keyed on `id`, with a cursor, re-runnable, and never inside a single long transaction. |
| **Dual-write / dual-read on cutover** | When the costing/quota path moves out of `CallRecord.save()` (P1), records are written by both the old and new path and compared before the old path is removed. |
| **Tenant-by-tenant rollout** | Behavior changes are gated per `Company`. The 3CX SF pilot and SAMNAN absorb risk first; Smasco (highest volume) cuts over last. Smasco and SAMNAN are never simultaneously mid-cutover. |
| **Reversible by design** | Each phase lists a concrete rollback. P0 fixes are feature-flagged or are pure additions (an index, a config value) that can be dropped without data loss. |
| **Measure on live data** | Each exit criterion includes a validation query run against the production `cdr` DB (read-only user `read`) so "done" is evidence, not opinion. |

> **Heavy synchronous save is the structural risk that constrains sequencing.** `CallRecord.save()` (`cdr3cx/models.py:194`) synchronously does country lookup, `categorize_call()` (regex over `company.call_patterns`), `calculate_total_cost()`, and `update_user_quota()` — inside the socket thread, with per-record `print()`/`logger.info`. Worse, the `apply_pattern_to_call_records` post_save signal (`cdr3cx/models.py:58`) re-saves **all** matching historical CallRecords whenever a `CallPattern` is saved (unbounded, synchronous). Until this is decomposed (P1), we cannot safely increase ingestion throughput or add multi-vendor sources.

---

## 2. Phase Overview (one-page timeline)

Effort tags: S ≤ 1 wk, M ≈ 2–4 wks, L ≈ 1–2 mo, XL ≈ 2–4 mo (one squad of ~3–5 engineers). Durations are calendar estimates assuming one squad; phases overlap where dependencies allow.

| Phase | Theme | Primary Goal | Effort | Indicative Window | Hard Dependency |
| --- | --- | --- | --- | --- | --- |
| **P0** | Stabilize & Secure | Stop the bleeding: data-quality bug, perf, alert misdelivery, socket lockdown, secrets, **real worker** | M | Weeks 0–3 | none |
| **P1** | Data & Ingestion Foundation | Canonical schema + ACD entities; idempotent **async** ingestion (DB-pull connector); decompose `save()`; backfill/normalize history | XL | Weeks 2–14 | P0 (worker, index) |
| **P2** | Call-Center Evaluation v1 | Queue/Agent/State models, KPI engine, supervisor wallboard + agent dashboard, SLA alerts — **3CX SF pilot** | XL | Weeks 10–24 | P1 schema |
| **P3** | Reporting / UI Overhaul | Report catalog, design system, RTL, **working** scheduled-report engine, exports | L | Weeks 18–30 | P0 worker, P1 indexes |
| **P4** | Billing-Grade & Alert Engine | Invoices/payments/tax/multi-currency; correct quota; ThresholdPolicy alert-rules engine | L | Weeks 26–40 | P1 (costing moved async) |
| **P5** | Multi-Vendor Adapters | Cisco CUCM first via adapter pattern; API/partner enablement | XL | Weeks 36–56 | P1 canonical schema |
| **P6** | Intelligence / AI | Transcription, sentiment, QA automation, forecasting, anomaly detection | XL | Weeks 50+ | P2 agent layer, P5 data breadth |

Cross-references: P1 ↔ [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md) and [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md); P2 ↔ [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md) and [13-Call-Center-KPI-and-Metrics-Reference.md](13-Call-Center-KPI-and-Metrics-Reference.md); P3 ↔ [07-Reporting-Dashboards-and-UI-UX.md](07-Reporting-Dashboards-and-UI-UX.md); P4 ↔ [06-Billing-Quota-and-Fraud.md](06-Billing-Quota-and-Fraud.md) and [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md); P5 ↔ [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md); security throughout ↔ [09-Security-and-Compliance.md](09-Security-and-Compliance.md).

---

## 3. P0 — Stabilize & Secure (Weeks 0–3, Effort M)

**Goal:** Make the live system *correct, observable, and not actively dangerous* with the smallest, most reversible changes. This phase delivers visible wins (the call-statistics table starts showing data) and unblocks everything downstream by standing up a real async runtime. Backlog source: the "Top 10 Critical Fixes" in [11-Gap-Analysis-and-Feature-Backlog.md §1](11-Gap-Analysis-and-Feature-Backlog.md).

### Workstreams

| # | Workstream | Severity | Effort | Current → Target |
| --- | --- | --- | --- | --- |
| P0.1 | **Flagship case-bug hotfix** | Critical | S | Exact-case filters `Q(to_type='Ivr')` drop ~half the rows → filter case-insensitively (`__iexact` / `LOWER()`) in `callcenter_views.py` and reports |
| P0.2 | **`call_time` index** | Critical | S | No index on `call_time` → seq-scan of 1.49M rows on every report → composite `(company_id, call_time)` built `CONCURRENTLY` |
| P0.3 | **Fix alert recipient** | High | S | `recipient = 'khuram2025@gmail.com'` hardcoded at `cdr3cx/models.py:371` → resolve to extension/tenant owner email |
| P0.4 | **Lock down the socket** | Critical | S | Auth-less TCP listener on public ports 8000/8005 (scanners hit it — `records.txt` full of `androxgh0st` probes) → firewall to known PBX source IPs + per-tenant IP allowlist |
| P0.5 | **Production security baseline** | Critical | S | `DEBUG=True`, `ALLOWED_HOSTS=['*']`, hardcoded `SECRET_KEY` (`settings.py:22-27`), DB creds in source → env-based secrets, `DEBUG=False`, explicit hosts, TLS at nginx |
| P0.6 | **Stand up Celery worker + Redis broker** | Critical | M | No worker, no cron (verified) → `celery.service` + `celery-beat.service` under systemd; Redis already present (`:6379`) doubles as broker |
| P0.7 | **Tame the `print`/signal storm** | High | S | Per-record `print()`/`logger.info` and unbounded `apply_pattern_to_call_records` re-save → gate debug logging behind level; bound/queue the pattern re-apply |

### P0.1 — the case fix (illustrative)

The complaint in `/home/ubuntu/3CX/issues.txt` ("why the call Statics not showing data in the table") is this bug. Minimal, reversible fix while the proper ingest-time normalization is built in P1:

```python
# cdr3cx/callcenter_views.py — before
qs.filter(Q(to_type='Ivr') | Q(final_type='Extension'))
# after (case-insensitive; recovers the silently-dropped ~half)
qs.filter(Q(to_type__iexact='ivr') | Q(final_type__iexact='extension'))
```

Also replace the broken missed-call heuristic: `reason_terminated == 'NoAnswer'` matches **zero** rows (the real values are `src_participant_terminated`, `TerminatedBySrc`, `dst_participant_terminated`, …, themselves mixed-case). Use the reliable signal verified live — `time_answered IS NULL` (461,602 unanswered / 1,030,590 answered). See [13-Call-Center-KPI-and-Metrics-Reference.md](13-Call-Center-KPI-and-Metrics-Reference.md) for the corrected definitions.

### P0.2 — the index (online, safe on 1.49M rows)

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS cdr_callrecord_company_calltime
  ON cdr3cx_callrecord (company_id, call_time DESC);
```

`CONCURRENTLY` avoids the `ACCESS EXCLUSIVE` lock, so live ingestion and dashboards keep running during the build. Validate by re-running a dashboard date-range query with `EXPLAIN (ANALYZE)` and confirming an index scan replaces the sequential scan.

### Exit criteria (P0)

- The call-center dashboard and reports return non-empty results for both tenants; a count via the corrected `__iexact` filter is materially higher than the old exact-case count (target: ≈ doubling on `ivr`/`extension`).
- `EXPLAIN ANALYZE` on a 30-day dashboard query shows `Index Scan` on the new composite index, not `Seq Scan`.
- A test quota alert is delivered to the *extension owner's* address, not `khuram2025@gmail.com`.
- External scanners can no longer reach ports 8000/8005 (verify from an off-network host); only configured PBX IPs connect.
- `DEBUG=False`, no secrets in source (`git grep` clean), TLS serving `connect.zentryc.com`.
- `celery -A cdr inspect ping` returns a live worker; `celery-beat` is scheduled; a no-op periodic task is observed running.

### Risks & rollback (P0)

| Risk | Mitigation / Rollback |
| --- | --- |
| `DEBUG=False` surfaces a 500 hidden by debug pages | Stage the change; pre-test all top URLs; rollback = flip env var, no redeploy of code |
| `CONCURRENTLY` build fails mid-way (leaves invalid index) | Drop the invalid index and retry off-peak; no data impact |
| Tighter firewall blocks a legitimate PBX whose IP changed | Keep socket service running; allowlist is config — add the IP; do not decommission socket in P0 |
| New worker mis-routes alerts | Worker only runs new opt-in tasks in P0; existing inline behavior untouched |

---

## 4. P1 — Data & Ingestion Foundation (Weeks 2–14, Effort XL)

**Goal:** Establish the canonical, vendor-neutral data model and a robust, idempotent, **asynchronous** ingestion pipeline, and normalize the 1.49M rows of history. This is the load-bearing phase: P2–P6 all sit on it. Detailed design lives in [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md), [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md), and [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md).

### Workstreams

| # | Workstream | Effort | Detail |
| --- | --- | --- | --- |
| P1.1 | **Canonical CallRecord superset** | M | Add (nullable) `direction`, `ring_time`, `wait_time`, `hold_time`, `wrap_time`, `abandoned`, `call_disposition`/normalized reason, `queue_id`, `agent_id`, `currency`, `ingest_transport`. Schema already has `source_pbx`/`external_id`/`correlation_id`/`raw_data` — reuse them. |
| P1.2 | **ACD entity layer** | L | New models `Queue`, `Agent`, `AgentState`, `Disposition`/`WrapCode`, `CallLeg`, `Recording` — vendor-neutral so 3CX *and* Cisco/Webex/Zoom states map onto them. |
| P1.3 | **DB-pull connector (3CX v20 `cdr_output`/`cdr_billing`)** | L | Read-only, cursor-keyed (`cdr_started_at` + GUID `cdr_id`), maps `cdr_id → external_id/correlation_id`, full row → `raw_data`. Runs as a Celery task. Strategic path; fixes truncation/ordering/dedup in one move. |
| P1.4 | **Abstract `CdrSource` adapter** | M | `ThreeCXDbSource`, `ThreeCXSocketSource`, `ThreeCXCsvSource` behind one interface (`fetch → normalize → correlate → upsert`). PBX quirks (field order, casing, version) stay inside the adapter. |
| P1.5 | **Ingest-time normalization** | M | Canonicalize `*_type` and `reason_terminated` to lowercase enums at ingest, so socket **and** DB feeds are consistent and the case bug can never recur. |
| P1.6 | **Decompose `CallRecord.save()`** | L | Bulk-insert raw normalized rows; a separate **idempotent** enrichment task does country lookup, `categorize_call`, costing, and quota deduction (with `select_for_update`). Remove inline `print`/signal re-save. |
| P1.7 | **Harden the socket fallback** | S | Loop `recv()` until connection close (fixes the hard `recv(1024)` truncation at `socket_server.py:31`); PBX-IP allowlist; treat as best-effort, reconciled by the DB pull. |
| P1.8 | **Historical backfill & normalization** | L | Batched, resumable job: normalize case across all 1.49M rows; derive `wait_time`/`talk`/`answered`/`abandoned` from existing timestamps; tag `ingest_transport='socket'` for legacy rows. |

### Migration discipline for P1.1 (expand → migrate → contract)

1. **Expand:** add new columns nullable/defaulted (no lock impact; values backfilled lazily).
2. **Migrate:** dual-write — the new async enrichment populates the canonical fields while the legacy inline path is still authoritative; reconcile counts and a sampled diff between old and new costing/quota.
3. **Contract:** once parity holds in production for ≥1 release, remove the inline costing/quota from `save()` and the unbounded post_save signal.

### Validation on live data (P1)

- **Shadow reconciliation:** for a fixed window, the DB-pull connector's normalized output matches the socket feed's records (same call count ± expected dedup), and `raw_data` round-trips. Run on the 3CX SF pilot and SAMNAN before Smasco.
- **No regression in totals:** `SELECT company_id, date_trunc('day',call_time), count(*)` daily histograms are unchanged after backfill (normalization must not drop or duplicate rows).
- **Costing parity:** sampled `total_cost`/quota deltas between old inline path and new async path are zero within rounding.
- **Idempotency:** re-running the connector over an overlapping window produces **no** duplicate rows (verified by `upsert` on `(source_pbx, external_id)`).

### Risks & rollback (P1)

| Risk | Mitigation / Rollback |
| --- | --- |
| Backfill normalization corrupts a column | Run in batches into a *shadow* normalized column first; swap only after validation; legacy column retained for one release as rollback |
| 3CX DB is localhost-only / unreachable per tenant | Per-tenant transport selection: DB-pull where reachable, hardened socket/CSV otherwise; `ingest_transport` records lineage |
| Async enrichment lags under load | Backpressure + separate queue; socket fallback still captures raw rows; enrichment is replayable |
| Quota race under concurrent inserts persists | `select_for_update` is part of P1.6; validate under concurrent-insert load test before contract step |

---

## 5. P2 — Call-Center Evaluation v1 (Weeks 10–24, Effort XL)

**Goal:** Deliver credible ACD analytics and agent/supervisor evaluation for the **priority 3CX San Francisco call-center tenant**, replacing today's heuristic, half-blind module. Full design in [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md); metric formulas in [13-Call-Center-KPI-and-Metrics-Reference.md](13-Call-Center-KPI-and-Metrics-Reference.md).

### What changes vs today

The current module (`cdr3cx/callcenter_views.py`) infers "call-center calls" from `to_type=='Ivr'` or display-name matching, infers agents from `final_dispname`, runs **24 per-hour COUNT scans + 7×3 daily-trend scans** over unindexed rows, and `call_back_tracking` runs **N+1** nested queries. There are **no** real ACD metrics. P2 replaces this.

### Workstreams

| # | Workstream | Effort | Detail |
| --- | --- | --- | --- |
| P2.1 | **Queue/Agent/State population** | L | Populate the P1.2 entities. Source real queue/agent data from 3CX DB views (`callcent_queuecalls_view`, `extensions_by_queues_view`) where available; derive from normalized CDR otherwise. |
| P2.2 | **KPI engine** | L | Computable-today set from CDR: Service Level (answered within configurable target / (answered+abandoned)), ASA, Average/Longest Wait, Abandonment (+ short-abandon threshold), talk-based AHT. Pre-aggregated, indexed, set-based `GROUP BY date_trunc` — not 24 COUNTs. |
| P2.3 | **ThresholdPolicy (per-tenant/per-queue)** | M | One config for SLA target seconds, short-abandon seconds, alert thresholds — drives KPI formulas, wallboard colors, **and** alerts (shared source of truth). |
| P2.4 | **Supervisor wallboard** | L | Real-time over the existing Channels/Redis/daphne path: calls waiting, longest/oldest wait, agents available/on-call/not-ready, live SL. Driven by a live queue feed, **not** the CDR table. |
| P2.5 | **Agent dashboard** | M | Personal AHT, wrap time (once captured), answered%, transfer rate, with each number paired to its target. |
| P2.6 | **SLA breach alerts** | M | Tiered amber/red alerts on the same ThresholdPolicy, delivered via the P0.6 worker + notifications app. |
| P2.7 | **Agent-state capture (stretch)** | L | For PRO/ENT on-box tenants, optionally subscribe to the 3CX Call Control API WebSocket for live agent state → enables Occupancy/ACW/Adherence later (never a core-ingest dependency). |

### Validation on live data (P2)

- Service Level / ASA / Abandonment computed from CDR reconcile against 3CX's own native Queue/SLA reports (where the SF tenant is PRO+) within tolerance.
- Wallboard tiles update sub-second over WebSocket under a simulated call burst; no query hits the `cdr3cx_callrecord` table for live state.
- The SF pilot supervisor signs off that the metrics match floor reality (acceptance with a real stakeholder).

### Risks & rollback (P2)

| Risk | Mitigation / Rollback |
| --- | --- |
| Metrics depend on data CDR lacks (Occupancy, true ACW) | Ship the CDR-derivable subset first (SL/ASA/Abandon/Wait); state-derived metrics gated behind P2.7 agent-state feed |
| New wallboard load impacts daphne | Separate Channels group per tenant; load-test; old dashboard remains reachable behind a flag |
| 3CX DB views unavailable on a tenant edition | Fall back to normalized-CDR inference; clearly label which metrics are exact vs inferred |

---

## 6. P3 — Reporting / UI Overhaul (Weeks 18–30, Effort L)

**Goal:** A modern, role-based reporting and dashboard experience with a **working** scheduled-report engine, exports, a design system, and RTL support (TIME_ZONE is `Asia/Riyadh`; Arabic tenants need RTL). Design detail in [07-Reporting-Dashboards-and-UI-UX.md](07-Reporting-Dashboards-and-UI-UX.md).

### Workstreams

- **P3.1 — Scheduled-report engine (M):** hourly/daily/weekly/monthly recurrence, selectable window + timezone, recipient/metric/filter selection, PDF/XLSX/CSV/HTML, email + FTP delivery. **This only works because P0.6 stood up the worker/beat** — today this feature is dead code.
- **P3.2 — Report catalog (L):** a prebuilt library (target 50+) with cradle-to-grave per-call drill-down via `correlation_id`, progressive disclosure, brush-to-zoom time series.
- **P3.3 — Design system + widgets (M):** drag-drop count/chart/table widgets, per-user + shared + default dashboards, light/dark mode.
- **P3.4 — RTL + i18n (M):** RTL layouts and Arabic localization.
- **P3.5 — Materialized rollups (M):** pre-aggregated daily/hourly rollup tables to keep dashboards fast at scale.

**Exit criteria:** a scheduled report is created in the UI and arrives by email + FTP on schedule in the chosen timezone; a report renders in RTL; dashboard p95 load < 1s on a rollup-backed query.

**Risks/rollback:** scheduled jobs misfire → idempotent task design + dedupe key per (report, window); rollups drift → nightly reconcile against source, rebuildable.

---

## 7. P4 — Billing-Grade & Alert Rules Engine (Weeks 26–40, Effort L)

**Goal:** Move from quota-deduction-only to a real billing system, and from ad-hoc emails to a configurable alert-rules engine. Detail in [06-Billing-Quota-and-Fraud.md](06-Billing-Quota-and-Fraud.md) and [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md).

### Workstreams

| # | Workstream | Effort | Detail |
| --- | --- | --- | --- |
| P4.1 | **Invoicing & payments** | L | New: Invoice, Payment, dunning, payment-gateway integration. None exist today (billing has only `FraudRule`/`FraudIncident`/`TaxRule`). |
| P4.2 | **Multi-currency + tax wiring** | M | Wire the 13-row `Currency` table and `TaxRule` into rating/invoicing (currently schema/plumbing only). |
| P4.3 | **Quota correctness** | M | Confirm `select_for_update` (from P1.6) eliminates the deduction race; restore balance-exceeded enforcement; integrate with `blockExternalCall.py`. |
| P4.4 | **Alert rules engine** | L | Generalize ThresholdPolicy (P2.3) into a tenant-configurable rules engine driving email/SMS/WhatsApp with escalations; 18,361 `FraudIncident`s already exist to drive fraud alerts. |

**Exit criteria:** an invoice is generated for a tenant in their currency with tax applied and reconciles to summed `total_cost`; a payment marks it paid; concurrent-insert load test shows no quota drift; an alert rule fires through escalation to the correct supervisor (not a dev address).

**Risks/rollback:** billing math errors are financially sensitive → shadow-invoice and reconcile against existing per-call `total_cost` before going authoritative; gateway integration behind a sandbox flag.

---

## 8. P5 — Multi-Vendor Adapters (Weeks 36–56, Effort XL)

**Goal:** Prove the vendor-neutral design by ingesting a second PBX family — **Cisco CUCM first** — through the same adapter pattern, then enable API/partner consumption. Architecture in [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md).

### Workstreams

- **P5.1 — `CiscoCucmCdrSource` (L):** SFTP file poller for CUCM CDR (call facts) + CMR (media quality) flat CSVs; map `globalCallID_callId + globalCallID_callManagerId → external_id/correlation_id`, join CMR (`VarJitter`, `latency`, `pktsLost`, MOS) into the QoS columns (which are 100% NULL today). No realtime push exists for CUCM — it is batched file ingest.
- **P5.2 — Version/edition detection (M):** the connector detects 3CX v20-U6 `cdr_output` vs legacy v18 `callhistory2/3` vs socket vs CSV per tenant and tags `ingest_transport`.
- **P5.3 — Future cloud adapters (L, optional):** Teams (Graph `callRecords`), Webex (Correlation ID poll, 5-min delay, ~1 req/min, shrinking retention), Zoom (`call_history`/`call_path`) — all polling clients respecting per-vendor delay/rate/retention.
- **P5.4 — Public API / partner enablement (M):** mature the DRF + ApiKey + WebhookSubscription surface (currently 1 ApiKey, 0 WebhookDeliveries — barely used) for partner consumption.

**Exit criteria:** a CUCM CDR/CMR pair is ingested and appears as a canonical CallRecord with QoS populated, indistinguishable in reporting from a 3CX record except for `source_pbx`; re-ingesting the same file is idempotent.

**Risks/rollback:** vendor schema drift → all vendor quirks isolated in the adapter, `raw_data` preserves the original for re-processing; per-vendor flag allows disabling a misbehaving source without touching others.

---

## 9. P6 — Intelligence / AI (Weeks 50+, Effort XL)

**Goal:** Layer differentiating intelligence on top of the now-rich, multi-vendor dataset. Deliberately last — it depends on the agent-state layer (P2), data breadth (P5), and recordings.

### Workstreams

- **P6.1 — Recording ingestion + transcription (L):** capture `recording_url`/files (CallRecord has none today), transcribe.
- **P6.2 — Sentiment + call summaries (L):** per the [claude-api](https://docs.anthropic.com) model family for summarization/classification of transcripts.
- **P6.3 — QA automation (L):** Scorecard/Evaluation/Calibration models; auto-score every interaction; supervisor calibration tooling.
- **P6.4 — Forecasting & anomaly detection (M):** volume/SL forecasting and KPI anomaly callouts feeding the alert engine.
- **P6.5 — CSAT/NPS surveys (M):** post-call survey subsystem feeding agent scorecards (net-new; none exist).

**Exit criteria:** a call is transcribed, sentiment-scored, auto-QA-scored, and the result is attached to the agent's scorecard; a forecast vs actual is shown to a manager.

**Risks/rollback:** AI cost/accuracy → start on a sampled subset; human-in-the-loop on QA; all AI outputs advisory, never auto-enforcing.

---

## 10. Team Shape & RACI

A single cross-functional squad (~3–5 engineers) can execute P0–P3 sequentially; P4–P6 benefit from a second squad once the foundation (P1) is stable. Suggested roles and responsibility split:

| Activity / Phase | Backend/Data Eng | Frontend/UX | DevOps/SRE | Product/Stakeholder | QA |
| --- | --- | --- | --- | --- | --- |
| P0 hotfixes (case, index, recipient) | **R** | C | C | A | C |
| P0 security + worker | C | I | **R** | A | C |
| P1 schema + ingestion + backfill | **R** | I | C | A | C |
| P2 call-center KPIs + wallboard | **R** | **R** | C | **A** (SF tenant) | C |
| P3 reporting/UI/RTL/scheduler | C | **R** | C | A | C |
| P4 billing + alerts | **R** | C | C | **A** | C |
| P5 multi-vendor adapters | **R** | I | C | A | C |
| P6 AI/QA | **R** | C | C | A | C |

R = Responsible, A = Accountable, C = Consulted, I = Informed. The 3CX San Francisco tenant owner is the **accountable** acceptance authority for P2; tenant admins for Smasco/SAMNAN are consulted on any change touching their billing or ingestion.

---

## 11. Cutover & Rollback Summary

| Phase | Cutover mechanism | Rollback |
| --- | --- | --- |
| P0 | Config flips (`DEBUG`, hosts, secrets, firewall), online index build, code hotfix behind small PR | Revert env/config; drop new index; revert PR — no data change |
| P1 | Shadow connector → dual-write costing/quota → contract after parity, tenant-by-tenant | Keep socket service + inline path live until contract; revert to inline if parity fails |
| P2 | New module behind per-tenant flag; SF first | Old call-center views remain reachable behind flag |
| P3 | New UI/reports opt-in per user/tenant | Legacy reports retained one release |
| P4 | Shadow-invoice/reconcile before authoritative; gateway in sandbox | Disable invoicing flag; quota path unaffected |
| P5 | Per-vendor source flag; CUCM isolated | Disable the source; 3CX unaffected |
| P6 | Advisory outputs, sampled rollout | Disable AI features; no operational dependency |

---

## 12. Relationship to Prior Work & the Backlog

- The line-items here are the *sequenced* form of the prioritized gaps in [11-Gap-Analysis-and-Feature-Backlog.md](11-Gap-Analysis-and-Feature-Backlog.md) — that document is the canonical severity/effort/impact source; this one is the execution order and safety contract.
- The recent git work (2026-05-12) that added vendor-neutral CDR fields, multi-currency/tax/fraud models, the public API + webhooks, the Channels wallboard, and a security baseline is **schema/plumbing that this plan finishes wiring**: P1 activates the vendor-neutral fields and adapter, P2 activates the wallboard, P3 activates scheduled reports, P4 activates currency/tax/fraud alerting, P5 activates the API for partners.
- The market/pricing/MENA-strategy narrative in `/home/ubuntu/3CX/enhancement/*.md` (product lines IPT Bill / IPT Insight / IPT Contact) remains the business framing; for engineering decisions, this document set governs.

**The single most important sequencing rule:** do P0 (especially the worker and the index) before anything else, and never let a phase's cutover put both Smasco and SAMNAN at risk at the same time. Everything else is negotiable; data safety is not.
