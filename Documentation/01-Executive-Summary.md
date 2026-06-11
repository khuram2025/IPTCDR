# Executive Summary

**Platform:** `connect.zentryc.com` — a multi-tenant 3CX call-accounting, billing, call-control and call-center analytics portal.
**Audience:** stakeholders and engineering leadership.
**Date:** 2026-06-05. **Status of facts:** every figure below was verified live against the production code and `cdr` PostgreSQL database on this date.

This summary distils a full architecture audit, three external research streams (modern 3CX integration, contact-center KPI science, competitor/multi-vendor benchmarking), and a reconciliation of prior planning work. The detail lives in documents [02](02-Current-System-Architecture-Audit.md)–[13](13-Call-Center-KPI-and-Metrics-Reference.md); start with [11-Gap-Analysis-and-Feature-Backlog.md](11-Gap-Analysis-and-Feature-Backlog.md) for the consolidated backlog and [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md) for the plan.

---

## 1. What the platform is today

A **Django 5.0.7 monolith** at `/home/ubuntu/3CX/cdr` serving two live tenants — **Smasco** (`listening_port` 8000) and **SAMNAN** (8005) — with **1,492,192 call records** ingested over ~22 months (2024-07 → 2026-06) at ~2,000–4,000 calls/day. 3CX pushes CDRs over a raw-TCP socket; nginx fronts a gunicorn web tier and a Daphne WebSocket tier; PostgreSQL 16 and Redis sit behind them.

It does the core job — it records calls, rates them against per-pattern SAR tariffs, enforces per-extension spend quotas, and renders dashboards and exportable reports. Recent work (May 2026) also landed the *scaffolding* for a vendor-neutral schema, a public REST API, a fraud engine, a real-time wallboard, and a security baseline.

**The headline:** the accounting core is real and carries genuine production load, but the "intelligent call-center," billing-SaaS, real-time, and multi-vendor layers are **largely plumbing that is either unwired or silently broken**. The single most important finding is that the flagship call-center module has been showing wrong or empty numbers for roughly six months, and nobody could see why.

## 2. What is broken right now (verified, high-severity, cheap to fix)

| # | Finding | Verified evidence | Fix effort |
|---|---------|-------------------|:---:|
| 1 | **The call-center dashboard silently drops 50–75% of its data.** Filters use exact case `to_type='Ivr'` / `final_type='Extension'`, but a 3CX upgrade changed the feed to lowercase. Capitalized through Jul 2025; **100% lowercase since Dec 2025**. | `Ivr`=112,642 vs `ivr`=136,928; `Extension`=37,603 vs 147,702 case-insensitive. `callcenter_views.py:52,68` | **S** |
| 2 | **The "missed call" filter matches *zero* rows.** Code tests `reason_terminated='NoAnswer'`, a literal that **does not exist** in the data (real values are `src_participant_terminated`, `TerminatedBySrc`, `Failed`…). | `0` of 1,492,192 rows match. `callcenter_views.py:57,105,158,291,363,403` | **S** |
| 3 | **The real-time wallboard is broken the same way** — it reports `missed=0` / ~100% answer rate permanently. | `realtime/snapshot.py:30-31` uses the same `NoAnswer` predicate | **S** |
| 4 | **No index on `call_time`** on a 1.49M-row table, yet every dashboard filters by it. `EXPLAIN` confirms parallel sequential scans; the call-center page fires **24 + 21** such scans per load. | `pg_indexes`: only `company_id`, `source_pbx`, `external_id`, `correlation_id` indexed | **S** |
| 5 | **Quota alerts never reach customers.** `send_quota_alert()` is **dead code (no callers)** *and* hardcodes the recipient to a developer address. | `cdr3cx/models.py:360–371` → `khuram2025@gmail.com` | **S** |
| 6 | **Fraud protection never acts.** All **18 fraud rules run in `shadow_mode`** (log-only); all **18,361 incidents are `status='open'`**, none auto-disabled an extension. | `billing_fraudrule`: 18×`shadow_mode=t` | **S–M** |
| 7 | **Nothing asynchronous actually runs.** No Celery worker and no app cron exist — every "scheduled report," quota reset, alert and webhook retry is effectively dead. | systemd has only gunicorn/daphne/socket_server | **M** |
| 8 | **Production is unhardened and the ingest socket is open to the internet.** `DEBUG=True`, `ALLOWED_HOSTS=['*']`, a committed `django-insecure-…` `SECRET_KEY` and DB credentials in source; the CDR socket on port 8000 has no auth and is already probed by `androxgh0st` scanners. | `settings.py:22,25,27,285`; `records.txt` | **S** |
| 9 | **Rating covers only 35.8% of calls.** 957,203 of 1.49M rows have `total_cost=0`; `raw_data`/`external_id`/`correlation_id` are **100% NULL** (no dedup/idempotency). | DB counts | **M** |

Items 1–5 and 8 are mostly **sub-day fixes** that, together, restore the product's credibility and resolve the open complaint in `issues.txt` ("why the call Statics not showing data"). They require neither new infrastructure nor new data — see the Top-10 in [11](11-Gap-Analysis-and-Feature-Backlog.md) and the safe sequencing in [12](12-Migration-Plan-and-Phased-Roadmap.md).

## 3. What is strategically missing

- **There is no real ACD model.** No `Queue`, `Agent`, `AgentState`, `Disposition`, `Recording`, or `CallLeg`; agents and queues are *guessed* from display-name strings. Consequently the metrics a call-center is actually managed by — **Service Level, ASA, AHT, occupancy, adherence, true abandonment, FCR** — cannot be computed. Some (SL, ASA, abandonment, wait, answered%) become available *immediately* once items 1–4 are fixed; the rest need a new agent-state data feed. See [05](05-Call-Center-Evaluation-Module.md) and [13](13-Call-Center-KPI-and-Metrics-Reference.md).
- **It is not yet a billing product.** No invoices, payments, dunning, tax application, or multi-currency at runtime. See [06](06-Billing-Quota-and-Fraud.md).
- **Reporting/UI is a generic admin theme** (Velzon Bootstrap 5, with a Bootstrap 4 form pack mismatched against it); RTL/Arabic CSS is shipped but never linked; there is no report builder and no working scheduled delivery. See [07](07-Reporting-Dashboards-and-UI-UX.md).
- **It is single-vendor in practice.** 100% of records are `source_pbx='3cx'`. A vendor-neutral adapter scaffold already exists (`cdr3cx/adapters/base.py`) but is empty and unwired — the planned Cisco CUCM / Teams / Webex / Zoom expansion has a foundation but no implementation. See [10](10-Multi-Vendor-and-Target-Architecture.md).
- **The ingest path is fragile and synchronous.** `recv(1024)` truncates long records; parsing is positional; country lookup, rating, quota deduction and three `post_save` handlers (wallboard, fraud, a blocking webhook POST) all run inside the single socket thread. See [03](03-CDR-Ingestion-and-3CX-Integration.md).

## 4. The target: an intelligent, vendor-neutral CX analytics platform

The destination is an **event-driven, vendor-neutral** platform: pluggable ingestion adapters (3CX first, Cisco CUCM next) normalize every source into one canonical `CallRecord`/`CallLeg` model on an ingestion queue; a worker enriches, rates and stores; rollups feed fast dashboards; a rules engine drives real-time wallboards and multi-channel alerts (email/SMS/WhatsApp/webhook) with supervisor/agent escalation; and an intelligence layer adds transcription, sentiment, QA automation, anomaly/fraud detection and forecasting. Crucially this is achievable as a **modular monolith first** — the existing Django app is a fine host — with services extracted only where scale demands. Full design in [10](10-Multi-Vendor-and-Target-Architecture.md).

## 5. The plan at a glance

The roadmap is sequenced so the **live database and active tenants are never put at risk** (expand→migrate→contract, `CREATE INDEX CONCURRENTLY`, tenant-by-tenant cutover). Full detail, exit criteria and rollback in [12](12-Migration-Plan-and-Phased-Roadmap.md).

| Phase | Window | Goal |
|---|---|---|
| **P0 — Stabilize & Secure** | Weeks 0–3 | Land the Top-10 fixes; stand up a Celery + Redis worker so async/scheduled features actually run; harden prod and lock down the socket. |
| **P1 — Data & Ingestion foundation** | Weeks 2–14 | Canonical schema + ACD entities; idempotent async ingestion; backfill/normalize the mixed-case history. |
| **P2 — Call-Center Evaluation v1** | Weeks 10–24 | Queues/agents/state, a correct KPI engine, supervisor wallboard + agent dashboard, SLA alerts — piloted on the **3CX San Francisco** call center. |
| **P3 — Reporting & UI overhaul** | Weeks 18–30 | Report builder, working scheduled reports, design system, dark mode, Arabic/RTL + i18n. |
| **P4 — Billing-grade + Alert rules engine** | Weeks 26–40 | Invoices/payments/tax/multi-currency; per-tenant threshold/escalation alerting. |
| **P5 — Multi-vendor adapters** | Weeks 36–56 | Cisco CUCM first, then Teams/Webex/Zoom; partner/API enablement. |
| **P6 — Intelligence / AI** | Weeks 50+ | Transcription, sentiment, automated QA scoring, forecasting, NL querying. |

## 6. Bottom line

The platform is a **solid accounting core wrapped in half-finished ambition**. The fastest, highest-leverage move is unglamorous: a one-to-two-week stabilization pass (Top-10) makes the existing call-center, wallboard, billing and fraud features *tell the truth* and pays for itself in restored stakeholder confidence. From that base, P1–P2 turn the cosmetic "call-center tab" into a genuine agent/supervisor evaluation product on the 3CX San Francisco pilot, and P3–P6 deliver the intelligent, vendor-neutral, billing-grade platform the business is aiming for. None of the early work requires risky architecture changes — it is debt paydown and correct foundations first, capability second.

> **Read next:** [11-Gap-Analysis-and-Feature-Backlog.md](11-Gap-Analysis-and-Feature-Backlog.md) (what to do) → [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md) (in what order) → [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md) (the priority module).
