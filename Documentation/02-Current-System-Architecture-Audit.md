# Current System Architecture Audit

This document is the engineering ground-truth audit of the platform that powers **https://connect.zentryc.com** — a multi-tenant Django call-accounting, billing, call-control and call-center analytics portal for 3CX. It maps the live process/deployment topology, the Django application surface, the end-to-end request and CDR data flows, and the cross-cutting technical debt that constrains every downstream initiative. It is written to be read alongside its siblings ([03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md), [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md), [09-Security-and-Compliance.md](09-Security-and-Compliance.md), [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md), [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md)), which carry the deep redesigns this audit only points toward.

## TL;DR / Key Takeaways

- **The system is a single Django 5.0.7 monolith** at `/home/ubuntu/3CX/cdr` fronted by nginx on port 80, with three independent runtime processes: gunicorn WSGI (`:8001`, web UI), daphne ASGI (`:8002`, WebSocket `/ws`), and a raw-TCP `socket_server.service` that ingests 3CX CDRs. PostgreSQL 16 and Redis back them. It serves **1,492,192 call records** across **2 tenants** (Smasco / port 8000, SAMNAN / port 8005).
- **There is no worker.** Despite Celery-shaped and "scheduled report" features in the codebase, `systemd` runs only gunicorn, daphne and socket_server, and `/etc/cron.d` has no application jobs (verified). Every async/scheduled/alerting feature is **effectively not running in production.**
- **The CDR socket performs heavy synchronous work per call.** `CallRecord.save()` (cdr3cx/models.py) does country resolution, regex categorization, costing and quota deduction inline inside the ingest thread, wrapped in dozens of `print()`/`logger.info()` calls per insert — see cdr3cx/models.py:194–248.
- **Production is configured as if it were a developer laptop:** `DEBUG = True`, `ALLOWED_HOSTS = ['*']`, a committed `django-insecure-...` `SECRET_KEY`, DB credentials in source, the entire `venv/` committed in the tree, no CI/CD, and nginx terminating **plaintext :80 only** (no TLS). Details and remediation in [09-Security-and-Compliance.md](09-Security-and-Compliance.md).
- **The ingest socket is unauthenticated and internet-exposed** (port 8000 receives `androxgh0st` scanner probes — cdr3cx/records.txt), with a hard `recv(1024)` read that truncates long records and no idempotency key. The full pipeline redesign lives in [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md).
- **Performance time-bomb:** there is **no index on `call_time`** (only `company_id`, `source_pbx`, `external_id`, `correlation_id`), yet essentially every report and dashboard filters by `call_time` range — sequential scans over 1.49M rows today, worse under multi-vendor growth. See [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md).

---

## 1. System Context & Purpose

The product is a **vendor-portal layer on top of 3CX PBX deployments**. 3CX itself records the calls; this platform ingests those CDRs, normalizes and prices them, enforces per-extension quotas, and presents billing, fraud, and (heuristic) call-center analytics through a Django web UI plus a real-time WebSocket wallboard. Today it is **single-vendor (3CX only)** — every one of the 1,492,192 `CallRecord` rows has `source_pbx = '3cx'` — but the schema and the stakeholder mandate point at a vendor-neutral future that must also ingest Cisco CUCM and other IP-telephony platforms across multiple call centers ([10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md)).

**Operating scale (live, verified 2026-06-05):** ~2,000–3,800 calls/day, spanning 2024-07-31 → 2026-06-05 (~22 months); 779 Extensions and 779 UserQuotas; 18,361 FraudIncidents; 11 CallPatterns. The public REST API is essentially dormant (1 ApiKey, 0 WebhookDeliveries). Two tenants are resolved purely by **the TCP listening port the CDR arrives on** (`Company.listening_port`): Smasco=8000, SAMNAN=8005.

This audit **supersedes, for engineering purposes,** the older market/strategy document set at `/home/ubuntu/3CX/enhancement/*.md` (the "IPT Bill / IPT Insight / IPT Contact" business plan authored 2026-05-12). That set remains a useful product-vision reference but is not an engineering source of truth; where its claimed capabilities are schema-only or unwired, this audit says so.

## 2. Process & Deployment Topology

The platform is one monolith executed as three OS processes, plus the data stores. There is a fourth process that *should* exist — an async worker — and its absence is a primary finding.

```
                          INTERNET
                              │
   3CX PBX (Active Socket) ───┼─── Browsers / API clients (HTTP/WS)
   one TCP conn per call      │              │
   plaintext, NO auth         │              │  HTTP/WS  :80 (plaintext, NO TLS)
        │                     │              ▼
        │            ┌──────────────────────────────────────────┐
        │            │  nginx  (sites-available/cdr, listen 80)  │
        │            │  server_name connect.zentryc.com ...       │
        │            └───────────────┬───────────────┬───────────┘
        │                            │ HTTP          │ WS /ws/
        │              proxy_pass 127.0.0.1:8001   proxy_pass 127.0.0.1:8002
        │                            ▼               ▼
        │            ┌───────────────────────┐  ┌───────────────────────┐
        │            │ gunicorn  WSGI :8001  │  │ daphne  ASGI :8002     │
        │            │ Django web UI/reports │  │ Channels consumers/WS  │
        │            └───────────┬───────────┘  └───────────┬───────────┘
        ▼                        │                          │
┌───────────────────────┐       │   ┌──────────────────┐   │
│ socket_server.service │       ├──►│ PostgreSQL 16    │◄──┤
│ raw TCP :8000 / :8005 │──────►│   │ :5432  db=cdr    │   │
│ thread-per-conn       │  CallRecord.save()           │   │
│ recv(1024) HARD READ  │  (synchronous: country,      │   │
└───────────────────────┘   categorize, cost, quota)   │   │
                                    └──────────────────┘   │
                              ┌──────────────────┐         │
                              │ Redis :6379      │◄────────┘
                              │ Channels + cache │
                              └──────────────────┘

   ┌───────────────────────────────────────────────────────────┐
   │  MISSING: async worker (Celery/RQ) + scheduler.            │
   │  systemd has gunicorn/daphne/socket_server only;           │
   │  /etc/cron.d has no app jobs. → "scheduled reports",       │
   │  async alerts, batch enrichment do NOT run in production.  │
   └───────────────────────────────────────────────────────────┘
```

**Verified facts behind this diagram:**

| Component | Evidence | Notes |
|---|---|---|
| nginx :80 → :8001 / :8002 | `/etc/nginx/sites-available/cdr:13` `listen 80;`, `:14` `server_name ... connect.zentryc.com`, `:29` `proxy_pass http://127.0.0.1:8002;` (WS), `:42` `proxy_pass http://127.0.0.1:8001;` (HTTP) | **No `listen 443` / TLS in the active vhost.** |
| gunicorn WSGI :8001 | `gunicorn_config.py:10` `bind = "127.0.0.1:8001"` | Synchronous web UI / reports. |
| daphne ASGI :8002 | `daphne.service` `ExecStart=... daphne -b 127.0.0.1 -p 8002 ... cdr.asgi:application` | WebSocket `/ws/*` (Channels). |
| socket_server | `socket_server.service` runs `cdr3cx/socket_server.py`; binds per `Company.listening_port` (`socket_server.py:161`) | Ports 8000/8005, public, unauthenticated. |
| PostgreSQL 16 :5432 | `settings.py:284-287` `NAME='cdr'`, `USER='read'`, `PASSWORD='Read@123'`, `HOST='localhost'` | DB creds hardcoded in source. |
| Redis :6379 | `settings.py:85` Channels layer host; also app cache | Channels backplane + cache. |
| **No worker / no cron** | `systemctl` lists only gunicorn/daphne/socket_server/nginx/postgres/redis; `/etc/cron.d` has only `e2scrub_all`, `sysstat` | **Critical operational gap.** |

The single co-located node is a simplicity win at this scale but a resilience and isolation liability: web, real-time, ingest, DB and cache share one host with no horizontal split, and the ingest socket's synchronous DB work competes directly with web request latency.

## 3. Django Application Map

The monolith is organized into ten Django apps under `/home/ubuntu/3CX/cdr/`. Responsibilities (and the most load-bearing models) are below; the call-center and billing internals are owned by sibling docs.

| App | Responsibility | Key models / entry points | Owning sibling doc |
|---|---|---|---|
| **cdr3cx** | Core domain: CDR model, ingest socket, pattern/category, quotas, call-center views, reports, extension auto-disable | `CallRecord`, `CallPattern`, `Quota`/`UserQuota`; `socket_server.py`, `callcenter_views.py`, `blockExternalCall.py` | 03, 04, 05 |
| **accounts** | Identity & tenancy | `CustomUser`, `Company` (tenant), `Extension`, `Role`/`UserRole`, `Currency`, `SmtpSettings`, `PasswordResetOtp` | 09 |
| **billing** | Rating, tax, fraud | `FraudRule`/`FraudIncident`, `TaxRule`, rating/services | 06 |
| **api** | Public REST surface | DRF + `ApiKey`, `WebhookSubscription`/`Delivery`, drf-spectacular | 03, 10 |
| **realtime** | Real-time wallboard | Channels consumers, wallboard snapshot | 08 |
| **notifications** | Notifications / email | `Notification`, email send | 08 |
| **security** | Hardening primitives | IP allowlist, audit log, password history/policy, dynamic per-tenant session timeout | 09 |
| **home** | Landing / shell | views/templates | 07 |

Two structural observations:

1. **`cdr3cx` is overloaded.** It owns ingestion, the canonical model, costing/quota logic, the entire call-center module, and reporting. This conflation is exactly why heavy compute ended up inside `CallRecord.save()` (Section 5) and why the call-center module reads the raw CDR directly rather than a purpose-built ACD model. The redesign in [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md) and [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md) extracts a dedicated metrics/agent/queue layer.
2. **Recent additions are plumbing, not product.** The 2026-05-12 git history added vendor-neutral CDR columns, multi-currency/tax/fraud models, the public REST API + webhooks, the Channels wallboard, and the security baseline. Live data shows much of it is **unwired**: 1 ApiKey / 0 WebhookDeliveries, QoS columns 100% NULL, and (per [05](05-Call-Center-Evaluation-Module.md)) no real ACD metrics. Treat these as foundations to *complete*, not features that *exist*.

## 4. End-to-End Request & Data Flows

### 4.1 Web request flow (browser → report)

```
Browser ──HTTP :80──► nginx ──proxy_pass :8001──► gunicorn ──► Django (WSGI)
   middleware: auth, tenant resolution, security app (IP allowlist, dynamic
   session timeout, audit log) ──► view ──► ORM query over PostgreSQL ──► template
```

The web tier is conventional Django. The risk is **not** the path but the queries it issues: the call-center dashboard runs **24 separate per-hour `COUNT` queries** (`callcenter_views.py:137` `for hour in range(24):` each ending in `.count()`) plus a 7×3 daily-trend block, each a full filtered scan of the **unindexed** `call_time` range over 1.49M rows; `call_back_tracking` runs nested per-number queries inside a Python loop (N+1). Every one of these competes with ingest on the same Postgres instance. Query-level remediation is in [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md); the module rebuild is in [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md).

### 4.2 CDR data flow (3CX → priced, quota-deducted record)

```
3CX PBX (Active Socket) ──TCP──► socket_server.py
  1. accept(); request = client_socket.recv(1024)          # socket_server.py:31  HARD 1024-byte read
  2. strip leading "Call ", split(',') into up to 20       # :39, :43  POSITIONAL fields
     positional fields  [0]call_time ... [19]final_dispname
  3. tenant = Company.objects.get(listening_port=port)     # :24, :161
  4. CallRecord(...).save()                                # SYNCHRONOUS heavy work, Section 5
        └─ country (phonenumbers) → categorize_call() (regex over patterns)
           → calculate_total_cost() → super().save() → update_user_quota() (DB writes)
```

This path has **no framing** (one CDR per TCP connection, single `recv`), **no authentication**, **no idempotency/dedup/sequence key**, and a **positional parser** that silently corrupts every column if a 3CX admin reorders the CDR field set. It is also where the flagship data-quality defect originates: the `*_type` tokens arrive in mixed casing (e.g. `Ivr` vs `ivr`, `Extension` vs `extension`) and are never normalized, so the case-sensitive call-center filters (`Q(to_type='Ivr')` at `callcenter_views.py:52`, `final_type='Extension'` at `:68`) silently drop roughly half the relevant rows — matching the open complaint in `/home/ubuntu/3CX/issues.txt`. The full transport redesign (read-until-close framing, IP allowlist, configuration-driven field mapping, and a strategic pull connector off the 3CX database) is in [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md); the casing fix and normalization layer are detailed in [04](04-Data-Model-and-Database-Performance.md) and [05](05-Call-Center-Evaluation-Module.md).

## 5. The Synchronous-Ingest Anti-Pattern (Architecture Hotspot)

The most consequential architectural defect is that **business compute runs inside the ingest thread**. `CallRecord.save()` (cdr3cx/models.py:194–248) executes, per call, on the socket-server thread:

```python
# cdr3cx/models.py (excerpt, paraphrased)
def save(self, *args, **kwargs):
    logger.info("--- Starting save process for CallRecord ---")
    print("--- Starting save process for CallRecord ---")     # :196  console spew per insert
    ...
    self.country = ...                                         # phonenumbers lookup
    self.categorize_call()                                     # :224  regex over company.call_patterns
    self.calculate_total_cost()                                # :228  rate × ceil(minutes)
    super().save(*args, **kwargs)
    self.update_user_quota(old_total_cost)                     # :240  DB writes, NO select_for_update
```

Four compounding problems:

| # | Problem | Evidence | Impact |
|---|---|---|---|
| 1 | Heavy work serialized in the ingest thread | `categorize_call()`, `calculate_total_cost()`, `update_user_quota()` all inline in `save()` (models.py:224–240) | Ingest throughput capped by per-call compute; web tier contends for the same DB. |
| 2 | Debug `print()` + `logger.info()` on every insert | dozens across `save()`/`categorize_call()`/`calculate_total_cost()` (e.g. models.py:196–248) | I/O and log volume scale with call volume (debug.log already ~1.1 MB). |
| 3 | Quota deduction without row locking | `update_user_quota()` has **no `select_for_update`** | Race condition / lost updates under concurrent inserts → incorrect balances. See [06-Billing-Quota-and-Fraud.md](06-Billing-Quota-and-Fraud.md). |
| 4 | Unbounded post-save reprocessing | `apply_pattern_to_call_records` `post_save` signal (models.py:57) re-saves **all** matching historical `CallRecord`s whenever a `CallPattern` is saved | Saving one pattern can trigger a synchronous re-cost storm across the table. |

**Current → target.** Today: parse → synchronous enrich → write, all on one thread, with no idempotency. Target: the ingest path performs a fast, idempotent **raw upsert** keyed on a stable call id; a **separate worker** then enriches (country, categorize, cost, quota-with-`select_for_update`) idempotently and in bulk. This requires the missing worker process (Section 6) and is specified across [03](03-CDR-Ingestion-and-3CX-Integration.md) (decoupled ingest) and [06](06-Billing-Quota-and-Fraud.md) (safe quota math).

## 6. Cross-Cutting Technical Debt

| Area | Current state (evidence) | Risk | Recommendation (target) | Sev | Eff |
|---|---|---|---|---|---|
| **Production config** | `DEBUG = True` (settings.py:25), `ALLOWED_HOSTS = ['*']` (:27), committed `SECRET_KEY` (:22) | Stack-trace info leak, host-header attacks, forgeable signatures | `DEBUG=False`, explicit host allowlist, rotate `SECRET_KEY` to env/secret store | Critical | S |
| **Secrets in source** | DB user/pass `read`/`Read@123` (settings.py:284–287); SMTP password in commented code (:312) | Credential exposure via repo/backups | Move all secrets to env / vault; rotate exposed creds | Critical | S |
| **No TLS** | nginx active vhost `listen 80;` only (sites-available/cdr:13) | Plaintext creds/CDR/session over the wire | Terminate TLS (443 + HSTS), redirect 80→443 | Critical | S |
| **No async worker / scheduler** | systemd: gunicorn/daphne/socket_server only; no app cron | "Scheduled reports", async alerts, batch enrichment **silently do nothing** | Add a Celery/RQ worker + beat (or systemd timers) as a first-class process | Critical | M |
| **Synchronous heavy ingest** | `CallRecord.save()` inline compute (models.py:194–248) | Throughput ceiling, web/ingest contention | Decouple: raw upsert + worker enrichment (Section 5) | High | L |
| **Debug logging per insert** | `print()`/`logger.info()` throughout `save()` | Log bloat, I/O cost, no structured logging | Replace with structured, leveled logging; drop per-insert prints | High | S |
| **No `call_time` index** | indexes only on `company_id`/`source_pbx`/`external_id`/`correlation_id` (verified `pg_indexes`) | Seq scans over 1.49M rows on every report | Add composite `(company_id, call_time)` index — see [04](04-Data-Model-and-Database-Performance.md) | High | S |
| **Committed `venv/`** | `/home/ubuntu/3CX/cdr/venv` tracked in git | Bloated repo, non-reproducible deps, platform-specific binaries | Remove from VCS; pin via `requirements.txt`/lock; build in CI | Medium | S |
| **No CI/CD** | No `.github/` or pipeline; deploy is manual on-box | No automated tests/lint/security gate; risky manual deploys | Introduce CI (lint, test, migration check, security scan) + deploy pipeline | High | M |
| **Unauthenticated public ingest socket** | `recv(1024)` (socket_server.py:31), no auth; `records.txt` full of `androxgh0st` probes | Spoofed/garbage CDRs, truncation, internet exposure | IP-allowlist PBX source, read-until-close framing, move strategic path to pull — [03](03-CDR-Ingestion-and-3CX-Integration.md) | High | M |
| **Misdirected quota alerts** | `recipient = 'khuram2025@gmail.com'` hardcoded (models.py:371) | All quota alerts go to a developer, never the owner | Resolve recipient from extension/tenant owner — [06](06-Billing-Quota-and-Fraud.md)/[08](08-Realtime-Alerts-and-Notifications.md) | High | S |
| **Positional CDR parser** | `split(',')` into fixed positions (socket_server.py:43, 68–70) | Field reorder on PBX silently corrupts all columns | Configuration-/column-name-driven mapping — [03](03-CDR-Ingestion-and-3CX-Integration.md) | High | M |

## 7. Operational Risks

- **Single point of failure / no isolation.** Web, WebSocket, ingest, DB and cache are co-located on one node. A query storm from the call-center dashboard (Section 4.1) can degrade ingest, and a CDR re-cost storm (Section 5, item 4) can degrade the web UI. There is no horizontal scaling story and no documented failover.
- **Silent feature failure.** Because no worker/cron runs, any code path that assumes "scheduled" or "async" execution returns success in code review but **never fires** in production. This is the most dangerous class of debt: it is invisible until a stakeholder asks why a scheduled report or alert never arrived. Validate every "scheduled"/"async" claim against the running process list before promising it.
- **Data-integrity drift.** Quota deduction without locking (Section 5, item 3) plus the mixed-casing data-quality defect (Section 4.2) mean both *money* (balances) and *metrics* (call-center counts) are quietly wrong today. These are correctness bugs, not cosmetic ones.
- **Observability gap.** "Logging" is unstructured `print()`/`logger.info()` debug spew; there is no metrics/tracing/alerting on the processes themselves. Operators cannot currently see ingest lag, dropped CDRs, or worker health (there is no worker to see).
- **Deploy risk.** Manual on-box deploys with a committed venv and no CI mean no reproducible build, no automated migration safety check, and no rollback discipline. The phased path to fix this is in [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md).

## 8. Prioritized Architecture-Debt Summary

The table below ranks the architecture-level items by severity and effort (S/M/L/XL). It is the architecture slice of the consolidated backlog in [11-Gap-Analysis-and-Feature-Backlog.md](11-Gap-Analysis-and-Feature-Backlog.md).

| Rank | Item | Severity | Effort | Why it is ranked here |
|---|---|---|---|---|
| 1 | Production hardening: `DEBUG=False`, host allowlist, secret rotation, **TLS** | Critical | S | Cheap, blocks active exploitation; gates everything else ([09](09-Security-and-Compliance.md)). |
| 2 | Introduce an async **worker + scheduler** process | Critical | M | Unlocks scheduled reports, alerts, batch enrichment — currently all dead. |
| 3 | Decouple ingest from enrichment (raw upsert → worker) | High | L | Removes the Section-5 hotspot; prerequisite for vendor scale ([03](03-CDR-Ingestion-and-3CX-Integration.md)). |
| 4 | Add `(company_id, call_time)` index + kill N+1 dashboard queries | High | S | Immediate, large latency win on every report ([04](04-Data-Model-and-Database-Performance.md)). |
| 5 | Normalize `*_type`/reason casing at ingest | High | M | Fixes the flagship "no data in stats" defect ([04](04-Data-Model-and-Database-Performance.md)/[05](05-Call-Center-Evaluation-Module.md)). |
| 6 | Harden the ingest socket (auth/allowlist, framing) | High | M | Closes public-internet exposure; stops truncation ([03](03-CDR-Ingestion-and-3CX-Integration.md)). |
| 7 | Safe quota math (`select_for_update`) + correct alert recipient | High | S | Money correctness ([06](06-Billing-Quota-and-Fraud.md)). |
| 8 | CI/CD + remove committed `venv/`; structured logging | High/Med | M | Reproducible, observable, gated delivery ([12](12-Migration-Plan-and-Phased-Roadmap.md)). |
| 9 | Extract an ACD/agent/queue model out of `cdr3cx` | High | XL | Foundation for real call-center evaluation ([05](05-Call-Center-Evaluation-Module.md)) and multi-vendor ([10](10-Multi-Vendor-and-Target-Architecture.md)). |

## 9. Where This Leads

The current architecture is a serviceable single-tenant-shaped monolith that has been asked to behave like a multi-tenant, multi-vendor analytics platform without the runtime (worker), the data model (ACD/agent/queue), the indexing, or the operational hardening that role demands. None of these are exotic; they are well-understood, sequenced changes. The recommended order is: **harden production and add a worker first** (cheap, unblocking), **then decouple ingest and index the data** (correctness + performance), **then build the vendor-neutral model and call-center layer** (the differentiating product work). The end-to-end ingestion redesign is in [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md), the data/performance work in [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md), the security baseline in [09-Security-and-Compliance.md](09-Security-and-Compliance.md), the target event-driven architecture in [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md), and the phased delivery plan in [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md).
