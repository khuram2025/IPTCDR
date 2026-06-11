# CDR Ingestion & 3CX Integration

This document is the engineering reference for how Call Detail Records (CDRs) reach the connect.zentryc.com portal today, why the current path is fragile, and what the strategic 3CX integration architecture should be. It walks the live `socket_server.py` pipeline line-by-line, catalogues its failure modes, surveys the full modern 3CX integration landscape (socket vs CDR-to-DB vs file vs Call Control/XAPI), and specifies a robust, vendor-neutral ingestion redesign plus a low-risk migration path. It pairs with [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md) (schema/indexing/partitioning) and [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md) (the adapter pattern and Cisco/Teams/Webex/Zoom expansion).

## TL;DR / Key Takeaways

- **We use the oldest of four 3CX integration paths.** All 1,492,192 CallRecords (`source_pbx='3cx'`) arrive over the legacy "Active Socket" CDR feed into `cdr3cx/socket_server.py`. It is a thread-per-connection TCP listener that reads exactly `recv(1024)` bytes once, strips a `Call ` prefix, and splits on commas into 20 positional fields. It is **not deprecated by 3CX**, but it is now the legacy path.
- **The listener has five structural defects:** a hard 1024-byte read that truncates long records (`socket_server.py:31`); a brittle **positional** parser that silently corrupts every column if a PBX admin reorders fields; **no authentication** on a public port (the `debug.log` and `records.txt` are full of `androxgh0st` and `GET /index.htm` internet-scanner probes); **no idempotency/dedup key**; and a **heavy synchronous `CallRecord.save()`** that runs country lookup, regex categorization, costing and quota deduction inline on the socket thread (`models.py:194-248`).
- **The strategic source is the 3CX internal PostgreSQL.** v20 Update 6 (2025) rewrote CDR storage into a flat `cdr_output` table (~41 fields, a GUID `cdr_id`, UTC timestamps) plus a linked `cdr_billing` table — explicitly positioned for BI/external reporting and ~10x faster. It carries the per-call GUID, granular timestamps, and (via queue/agent DB views) the real ACD data the socket feed lacks.
- **Recommendation:** keep a *hardened* socket listener only as a fallback/real-time tap, and make the strategic path a **PULL, vendor-neutral connector** that reads `cdr_output`/`cdr_billing` (or legacy `callhistory` on v18 boxes) over a read-only DB user, mapping `cdr_id → external_id`/`correlation_id` and the full row into `raw_data`. A `NormalizedCdr`/`PbxAdapter` scaffold already exists at `cdr3cx/adapters/base.py` but **has no concrete adapter and is not wired into the live path**.
- **Two blocking prerequisites apply to ingestion at any scale:** normalize the mixed-case `*_type`/`reason_terminated` tokens at ingest (the flagship bug that silently drops ~half the call-center records — see [05](05-Call-Center-Evaluation-Module.md)), and add the missing `(company_id, call_time)` index (see [04](04-Data-Model-and-Database-Performance.md)).

---

## 1. How CDRs flow today

### 1.1 Topology

3CX is configured for **Active Socket** CDR logging: each tenant PBX is the *TCP client* and dials out, one connection per completed call, to our listener's `IP:port`. The `socket_server.service` systemd unit runs `cdr3cx/socket_server.py`, which binds one listener thread per distinct `Company.listening_port` — Smasco on `8000`, SAMNAN on `8005` (`socket_server.py:160-172`). Tenant identity is resolved purely by **which port the bytes arrived on** (`get_company_for_port`, `socket_server.py:22-27`).

```
3CX PBX (Active client)  --TCP-->  socket_server.py listener thread (port == tenant)
                                          |
                                   recv(1024) once, strip "Call ", split(",")
                                          |
                                   CallRecord.objects.create(...)  -> save() (synchronous, heavy)
                                          |
                          country lookup + categorize + cost + quota deduction inline
```

There is **no Celery/worker and no app cron** in production (systemd has only `gunicorn`, `daphne`, `socket_server`). Every byte of business logic therefore executes *inside the socket thread*.

### 1.2 The receive-and-parse path (`socket_server.py`)

```python
# socket_server.py:31  — the truncation bug in one line
request = client_socket.recv(1024).decode('utf-8').strip()
...
# socket_server.py:39-43
if request.startswith('Call '):
    request = request[5:]
cdr_data = request.split(',')          # POSITIONAL split, no schema
...
# socket_server.py:67-69  — fixed positions, silently corrupt if reordered
from_type  = cdr_data[14].strip() if len(cdr_data) > 14 else ''
to_type    = cdr_data[15].strip() if len(cdr_data) > 15 else ''
final_type = cdr_data[16].strip() if len(cdr_data) > 16 else ''
```

The parser maps comma positions to columns, then calls `CallRecord.objects.create(...)` followed by an explicit `.save()` (`socket_server.py:103-127`). The 20-field order is the modern 3CX **Call-Flow** field set and is verified correct against this PBX's live feed in `/home/ubuntu/3CX/cdr/debug.log` (e.g. `Call 2026/06/05 07:37:06,0541116250,5490,00:00:09,...,extension,external_line,external_line,...`).

### 1.3 The 20-field positional format

| Pos | Field | Maps to CallRecord | Notes |
|----:|-------|--------------------|-------|
| 0 | `call_time` | `call_time` | `YYYY/MM/DD HH:MM:SS`, `/`→`-`, made tz-aware in `Asia/Riyadh` |
| 1 | `callee` | `callee`, `external_number` | also reused as `external_number` |
| 2 | `caller` | `caller` | used to resolve `Extension` for quota |
| 3 | `duration` | `duration` | `HH:MM:SS` → seconds (`socket_server.py:88-91`) |
| 4 | `time_answered` | `time_answered` | **NULL = call never answered** (461,602 rows, 30.9%) |
| 5 | `time_end` | `time_end` | |
| 6 | `reason_terminated` | `reason_terminated` | mixed-case duplicates (see §2.5) |
| 7 | `reason_changed` | `reason_changed` | |
| 8 | `missed_queue_calls` | `missed_queue_calls` | |
| 9 | `from_no` | `from_no` | truncatable by 1024-byte read |
| 10 | `to_no` | `to_no` | |
| 11 | `to_dn` | `to_dn` | |
| 12 | `final_number` | `final_number` | |
| 13 | `final_dn` | `final_dn` | |
| 14 | `from_type` | `from_type` | **mixed casing** (extension/Extension) |
| 15 | `to_type` | `to_type` | **mixed casing** (Ivr/ivr) |
| 16 | `final_type` | `final_type` | **mixed casing** |
| 17 | `from_dispname` | `from_dispname` | display name — **first to truncate** |
| 18 | `to_dispname` | `to_dispname` | |
| 19 | `final_dispname` | `final_dispname` | |

This order is **admin-configurable** in the 3CX console ("Manage CDR output fields" — enable/disable, reorder, fixed/dynamic length). 3CX does **not** guarantee the order; our parser assumes it. Older v18/v15-16 deployments emit a *different* set that includes `historyid`/`callid` (a stable call key) and even `bill-cost` — none of which our 20-field parser captures.

---

## 2. Failure modes

| # | Failure mode | Evidence | Severity | Effort to fix |
|---|--------------|----------|:--------:|:-------------:|
| F1 | **`recv(1024)` truncation** — one fixed-size read; long records (display names at pos 17-19) get cut off | `socket_server.py:31` | Critical | S |
| F2 | **Positional parser fragility** — reorder/add/remove a field on any tenant PBX and every column silently shifts | `socket_server.py:53-72` | High | M |
| F3 | **No authentication on a public port** — internet scanners actively hitting `8000` | `records.txt` (`androxgh0st`/`Graber`), `debug.log` (`GET /index.htm`) | Critical | S |
| F4 | **No idempotency / dedup / sequence** — no `cdr_id`; a TCP retransmit or replay double-inserts | `socket_server.py:103` (`create`, not `get_or_create`) | High | M |
| F5 | **Heavy synchronous save** — country lookup + regex categorization + costing + quota deduction inline on the socket thread, with `print()` and `logger.info()` on *every* insert | `models.py:194-248` | High | L |
| F6 | **Port-per-tenant coupling** — tenant identity == listener port; collisions/misconfig silently route to a "Default Company" | `socket_server.py:22-27, 160-172` | Medium | M |
| F7 | **Mixed-casing not normalized at ingest** — raw tokens stored verbatim, breaking downstream filters | DB: `Ivr` 112,642 + `ivr` 136,928 | Critical | S |
| F8 | **Unbounded re-save signal** — saving one `CallPattern` re-`save()`s every matching historical record | `models.py:57-79` | High | M |

### 2.1 F1 — the 1024-byte truncation

`client_socket.recv(1024)` reads *at most* 1024 bytes once and never loops. TCP does not preserve message boundaries; a CDR longer than the first segment (long display names, multiple participants) is silently truncated. The display-name fields (positions 17-19) are exactly where this manifests first. **Fix:** loop `recv()` until the peer half-closes (3CX sends one CDR per connection and closes), accumulating into a buffer before parsing.

### 2.2 F2 — positional parser

`cdr_data[14] == from_type` is true only for *this* PBX's *current* field configuration. A different tenant, a 3CX version with a different default set, or an admin who reorders the "Manage CDR output fields" screen will silently corrupt every column with **no error** — the split still "succeeds." This is intrinsic to the socket transport and is the strongest reason to make the strategic path read by **column name**, not position.

### 2.3 F3 — auth-less public listener

The listener binds `0.0.0.0` (`socket_server.py:144`) with no source check. `cdr3cx/records.txt` is a log of `androxgh0st` exploit probes, and `debug.log` shows live HTTP scanner traffic (`GET /index.htm`, `Host: 46.202.159.119:8000`) being parsed as a (rejected) "CDR." Any internet host can inject fabricated CDRs into a tenant simply by connecting to its port. **Fix (interim):** firewall + an application-layer allowlist of the known PBX source IP per tenant. **Fix (strategic):** move ingestion to an *outbound* pull (§4) so no inbound public port is needed at all. See [09-Security-and-Compliance.md](09-Security-and-Compliance.md).

### 2.4 F4/F5 — no dedup, heavy synchronous save

The socket feed carries no stable call key, so the listener can only `create()` blindly. There is no defence against a re-delivered or replayed record. Worse, each insert runs the full `CallRecord.save()` override (`models.py:194`), which inside a single transaction does: `get_country_from_number()` (phonenumbers), `categorize_call()` (iterates `company.call_patterns` running regex per pattern), `calculate_total_cost()`, then `update_user_quota()` (a `OneToOne` lookup + `deduct_balance()` write) — interleaved with `print()` and `logger.info()` on every line. The quota deduction uses **no `select_for_update`** (race under concurrent inserts) and `deduct_balance()` no longer blocks on exceeded balance (`models.py:341-351`). All of this executes on the socket thread, so ingest throughput is bounded by the slowest enrichment step. See [06-Billing-Quota-and-Fraud.md](06-Billing-Quota-and-Fraud.md) for the quota correctness issues.

### 2.5 F7 — mixed casing is created/persisted at ingest

The raw 3CX feed itself emits inconsistent casing, and the listener stores it verbatim. Live counts confirm the flagship data-quality bug:

```sql
-- to_type, verified 2026-06-05
 Extension |  84297      ivr       | 136928
 extension |  67967      Ivr       | 112642
```

Because the call-center module filters with **exact** case (`Q(to_type='Ivr')`, `final_type='Extension'`), it silently excludes the lowercase half — directly causing the open complaint in `/home/ubuntu/3CX/issues.txt` ("why the call Statics not showing data in the table"). `reason_terminated` has the same disease (`src_participant_terminated` vs `TerminatedBySrc`), so any `reason_terminated == 'NoAnswer'` filter matches **zero** rows. **This must be fixed in the ingest layer** so both socket and future DB feeds are consistent (see [05](05-Call-Center-Evaluation-Module.md) and [13-Call-Center-KPI-and-Metrics-Reference.md](13-Call-Center-KPI-and-Metrics-Reference.md)).

---

## 3. The modern 3CX integration landscape

3CX exposes call data four ways. Our portal uses only #1.

| # | Path | Transport | Richness | Dedup key | Queue/agent data | Availability | Verdict for us |
|---|------|-----------|----------|-----------|------------------|--------------|----------------|
| 1 | **Legacy Active/Passive Socket CDR** | Raw TCP push, 1 record/call | Low (configurable fields) | **None** | No | All editions | **Current** — keep hardened as fallback/tap |
| 2 | **CDR-to-Database** (`cdr_output` + `cdr_billing`) | Read-only PostgreSQL pull | **Highest** (~41 fields, GUID, UTC, billing) | `cdr_id` (GUID) | Via queue/agent **views** | v20 U6+ (DB on `127.0.0.1`) | **Strategic source** |
| 3 | **CDR-to-File / CSV** | File on disk, configurable fields | Medium | depends on fields | No | All editions | Low-coupling fallback |
| 4 | **APIs (XAPI + Call Control)** | REST/OData + WebSocket | Provisioning / real-time state | n/a | Call Control = live state | XAPI = **Enterprise only**; Call Control = on-box only | Real-time wallboard/agent-state, **not** bulk CDR |

### 3.1 Socket CDR (path 1) — not deprecated, but legacy

3CX staff confirmed for U6: *"We have not updated the CDR log files output. Remains as it is for now."* So the socket/file feed is **not removed** in v20 — but it will never gain the v20 `cdr_output` richness (GUID, granular UTC timestamps, billing join). It is safe to keep as a low-risk real-time tap; it is not safe to keep as the *only* source.

### 3.2 CDR-to-Database (path 2) — the strategic source

v20 Update 6 (2025) rewrote storage into a flat `cdr_output` table (~41 fields) plus a linked `cdr_billing` table joined by `cdr_id`. Key fields: `cdr_id` (GUID), `source_participant_id/_phone_number`, `destination_dn_name`, `cdr_started_at` / `cdr_answered_at` / `cdr_ended_at` (UTC), `termination_reason` + `termination_reason_details`, `creation_method`, `continuation_reason`. 3CX explicitly markets it for BI/external reporting (Power BI, Grafana, BigQuery, Snowflake, Kafka) with ~10x faster queries. The DB (`database_single`, user `phonesystem`) listens only on `127.0.0.1:5432` by default, so a collector must be **co-located** with each PBX or reach it through a secured tunnel/replica. **This is the only path that carries a real dedup key and the queue/agent data.**

### 3.3 Queue/agent/SLA data lives in DB views (not the socket)

Real call-center data is in 3CX DB views — `callcent_queuecalls_view` (queue call metrics), `extensions_by_queues_view` (agent-to-queue membership), plus `call_history_view`; recording metadata is in the `recordings` table (files default to `/var/lib/3cxpbx/Instance1/Data/Recordings`). Our portal currently **infers** agents and queues heuristically from `to_type=='Ivr'` and display names — the socket feed simply does not carry queue membership, polling attempts, agent login history, or abandonment-vs-no-answer. The priority 3CX San Francisco call-center tenant **requires** the DB path. Note that 3CX natively lacks agent wrap-up/ACW, occupancy, utilization, schedule adherence, and FCR — genuine gaps we can differentiate on (detailed in [05](05-Call-Center-Evaluation-Module.md) and [13](13-Call-Center-KPI-and-Metrics-Reference.md)).

### 3.4 APIs (path 4) complement, they don't replace

v20 has two distinct APIs, neither of which is a bulk historical CDR source: the **Configuration/XAPI REST API** (OData/OpenAPI, swagger at `/xapi/v1/swagger.yaml`) is **Enterprise-gated** and is for provisioning; the **Call Control API** (real-time call/participant state, DTMF, transfer over WebSocket; OAuth2 client_credentials) must be installed **self-hosted on-box**. Call Control is the right tool to later capture live **agent state / wrap-up** for the metrics 3CX won't feed us — but ingestion must **never depend on it**, because it is on-box-only and edition-gated.

### 3.5 Editions / version heterogeneity

Queues + reporting need **PRO** or higher; XAPI is Enterprise-only. (On 2026-04-23 3CX consolidated to FREE/Basic/PRO/AI — PRO adds queues/reporting/contact-center; AI adds transcription/sentiment.) **Tenants on Basic/StartUP have no queues, reporting, or API at all** — for them the socket/file CDR is the *only* data we get, which is precisely the market our advanced-analytics value proposition serves. Our fleet will be heterogeneous: some tenants on v18 (old socket field set, `callhistory2/3` tables), others on v20/U6 (`cdr_output`). The connector must **detect version/edition per tenant** and pick the right source automatically.

---

## 4. Recommended ingestion redesign

The objective is to eliminate F1-F8 at the architectural level and produce a single, vendor-neutral normalization pipeline. A scaffold already exists — `cdr3cx/adapters/base.py` defines `NormalizedCdr` (a dataclass with `source_pbx`/`external_id`/`correlation_id`/`raw_data`/QoS fields and `to_call_record_kwargs()`), an abstract `PbxAdapter`, and an `AdapterRegistry`. **But there is no concrete `ThreeCXDbSource`/`ThreeCXSocketSource`, and the live `socket_server.py` bypasses it entirely.** The redesign is to *use* this scaffold.

### 4.1 Target pipeline

```
SOURCE ADAPTER            ->  NORMALIZE          ->  BUFFER/QUEUE  ->  ENRICH (worker)        ->  PERSIST
ThreeCXDbSource (pull)        canonical casing,      Redis stream      country, categorize,       bulk upsert on
ThreeCXSocketSource (tap)     map by COLUMN NAME,    (durable)         cost, quota (FOR UPDATE)    (source_pbx, external_id)
ThreeCXCsvSource (file)       full row -> raw_data
CiscoCucmCdrSource (later)
```

Five design rules:

1. **PULL is the strategic path.** A per-tenant collector reads `cdr_output` + `cdr_billing` (v20 U6) — or `callhistory2/3` + `calldetails` on v18 — over a **read-only** DB user, on a polling cursor keyed by `cdr_started_at` + the GUID `cdr_id`. Map `cdr_id → external_id`/`correlation_id`; store the untouched row in `raw_data`. This eliminates F1 (no fixed read), F2 (column-name mapping is order-independent), F3 (outbound, no public port), and F4 (GUID is the idempotency key) in one move.
2. **Map by column name, never by position.** For the DB path this is inherent. For the surviving socket path, store the per-tenant "Manage CDR output fields" order as *configuration* so a reorder cannot silently corrupt columns.
3. **Normalize casing at ingest** into canonical lowercase enums (`extension`/`ivr`/`line`/`voicemail`/`endcall`; `src_participant_terminated`, …) regardless of transport, so socket and DB feeds agree and the call-center filters stop dropping half the data (F7).
4. **Move enrichment off the ingest thread.** The adapter bulk-inserts raw normalized rows; a **separate idempotent enrichment step** does country lookup, `categorize_call`, costing, and quota deduction *with `select_for_update`*. Per-record `print()`/`logger.info()` and the unbounded `apply_pattern_to_call_records` re-save signal (F8) must not run inline (F5).
5. **Idempotent upsert.** Use `update_or_create` (or `INSERT ... ON CONFLICT`) on `(source_pbx, external_id)` so re-polling an overlapping window never duplicates (F4).

### 4.2 Concrete `ThreeCXDbSource` sketch

```python
# cdr3cx/adapters/threecx_db.py  (does not exist yet — proposed)
from .base import PbxAdapter, NormalizedCdr, register_adapter

@register_adapter
class ThreeCXDbSource(PbxAdapter):
    source_pbx = "3cx"
    display_name = "3CX (cdr_output DB pull)"
    supports_pull = True

    def fetch_cdrs(self, since):
        # read-only connection to the PBX's database_single
        rows = self._read_only_query("""
            SELECT o.cdr_id, o.cdr_started_at, o.cdr_answered_at, o.cdr_ended_at,
                   o.source_participant_phone_number, o.destination_dn_name,
                   o.termination_reason, b.cost
            FROM cdr_output o
            LEFT JOIN cdr_billing b USING (cdr_id)
            WHERE o.cdr_started_at > %s
            ORDER BY o.cdr_started_at
        """, [since])
        for r in rows:
            yield NormalizedCdr(
                source_pbx="3cx",
                external_id=r["cdr_id"],          # GUID -> idempotency key
                correlation_id=r["cdr_id"],
                company_id=self.config["company_id"],
                caller=r["source_participant_phone_number"],
                callee=r["destination_dn_name"],
                call_time=r["cdr_started_at"],
                time_answered=r["cdr_answered_at"],
                time_end=r["cdr_ended_at"],
                reason_terminated=normalize_reason(r["termination_reason"]),
                raw_data=dict(r),                 # full row preserved
            )
```

```python
# Idempotent persistence — never double-insert on re-poll
CallRecord.objects.update_or_create(
    source_pbx=n.source_pbx, external_id=n.external_id,
    defaults=n.to_call_record_kwargs(),
)
```

### 4.3 Hardening the surviving socket listener

Even as a fallback, the listener must be fixed:

```python
# Replace socket_server.py:31 single read with a drain loop (fixes F1)
chunks = []
while True:
    data = client_socket.recv(4096)
    if not data:
        break
    chunks.append(data)
request = b"".join(chunks).decode("utf-8", "replace").strip()
```

Plus: reject connections whose source IP is not the tenant's known PBX (fixes F3); treat fields as **best-effort**, to be reconciled later by the DB pull; and route the parsed record through the *same* `NormalizedCdr` normalization (casing) and the *same* off-thread enrichment as the DB path.

### 4.4 Runtime reality

The off-thread enrichment and any polling collector require a **real worker** — production currently has no Celery and no cron, so the existing scaffold cannot run on a schedule today. Options: a long-running management command driven by `systemd` (lowest friction, fits the current ops model), or Celery/RQ on Redis (already present for Channels). This is a prerequisite for both ingestion redesign and the scheduled-report/alert engines in [07-Reporting-Dashboards-and-UI-UX.md](07-Reporting-Dashboards-and-UI-UX.md) and [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md).

### 4.5 Performance prerequisite

Every dashboard and the call-center module's 24 per-hour + 21 daily COUNT queries filter `call_time` over 1.49M rows, and there is **no index on `call_time`** (verified — only `company_id`, `source_pbx`, `external_id`, `correlation_id` are indexed). A `call_time`-range count today falls back to the `company_id` index and heap-scans. Add `(company_id, call_time)` *before* scaling ingestion volume. Full treatment in [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md).

---

## 5. Ingestion migration path (3CX-specific)

A phased, reversible cutover. Broader program sequencing is in [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md).

| Phase | Action | Outcome | Severity addressed | Effort | Rollback |
|------:|--------|---------|--------------------|:------:|----------|
| **0** | Add `(company_id, call_time)` index; add `ingest_transport` tag column | Reports/dashboards stop seq-scanning; lineage recorded | F-perf | S | Drop index/column |
| **1** | Harden socket: drain-loop `recv`, source-IP allowlist, casing normalization at ingest | Truncation, auth, mixed-casing fixed for live feed | F1, F3, F7 | S/M | Revert listener |
| **2** | Move enrichment off the socket thread (idempotent worker; `select_for_update`; drop inline `print`/re-save signal) | Throughput + quota correctness; ingest decoupled from rating | F4, F5, F8 | L | Re-enable inline save |
| **3** | Build `ThreeCXDbSource` (read-only `cdr_output`/`cdr_billing` pull); run **parallel** with socket; reconcile by `cdr_id` | Richest source; real dedup key; queue/agent data reachable | F2, F4 | L | Disable connector, keep socket |
| **4** | Promote DB pull to **primary** for v20/U6 tenants; demote socket to real-time tap/fallback | Strategic path live; socket only for SMB/Basic tenants | all socket F's | M | Re-promote socket |
| **5** | Generalize via the `PbxAdapter` registry → add `CiscoCucmCdrSource` (SFTP CDR/CMR) | Multi-vendor; same normalization pipeline | n/a | XL | Per-adapter toggle |

Phases 0-2 deliver immediate, low-risk wins on the existing socket feed. Phase 3 onward shifts the centre of gravity to the DB pull while the socket keeps running as a safety net, so there is no "big bang" cutover and every step is independently revertible. The Phase-5 adapter design — abstract `CdrSource` with `ThreeCXDbSource`/`ThreeCXSocketSource`/`ThreeCXCsvSource`/`CiscoCucmCdrSource` concretes, all emitting the vendor-neutral `NormalizedCdr` shape — is specified in [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md).

---

## 6. Cross-references

- **Schema, the missing `call_time` index, partitioning, and the new columns the metrics need (`direction`, `ring_time`, `wait_time`, `hold_time`, `wrap_time`, `abandoned`):** [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md).
- **What queue/agent/SLA data the DB path unlocks and the ACD model:** [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md).
- **Quota race condition, costing, and the hardcoded `khuram2025@gmail.com` alert recipient:** [06-Billing-Quota-and-Fraud.md](06-Billing-Quota-and-Fraud.md).
- **The adapter pattern generalized to Cisco CUCM / Teams / Webex / Zoom and the event-driven target architecture:** [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md).
- **Security hardening of the listener and prod settings (`DEBUG=True`, auth-less port):** [09-Security-and-Compliance.md](09-Security-and-Compliance.md).
- **System-wide topology and tech-debt context:** [02-Current-System-Architecture-Audit.md](02-Current-System-Architecture-Audit.md).

> The older `/home/ubuntu/3CX/enhancement/*.md` business-strategy set (IPT Bill / IPT Insight / IPT Contact, MENA roadmap) framed ingestion only at the market level. This document supersedes it for engineering purposes: the strategic move is a vendor-neutral, read-only **DB pull** connector, not the auth-less inbound socket.
