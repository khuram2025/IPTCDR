# Multi-Vendor Strategy & Target Architecture

This document defines how connect.zentryc.com evolves from a single-vendor 3CX call-accounting monolith into a **vendor-neutral telephony analytics platform** that can ingest 3CX today and Cisco CUCM, Microsoft Teams, Webex Calling, Zoom Phone and generic SIP next — without re-platforming each time. It specifies the canonical `CallRecord`/`CallLeg` field set, a concrete ingestion-adapter contract (anchored on the scaffold that *already exists* in the codebase), an event-driven target architecture, and where an intelligence/AI layer fits. It deliberately favours **modular-monolith-first pragmatism**: refactor cleanly inside the existing Django project now, extract services only when load or team boundaries demand it.

## TL;DR / Key Takeaways

- **The hard part is already half-built — and unused.** The schema carries vendor-neutral columns (`source_pbx`, `external_id`, `correlation_id`, `raw_data`, plus QoS) and `cdr3cx/adapters/base.py` defines a `NormalizedCdr` dataclass + a `PbxAdapter` ABC + an `AdapterRegistry`. But there is **no concrete adapter, the registry is empty, and nothing is wired into the live socket path** — all 1,492,192 rows still arrive via the legacy `socket_server.py` and bypass the abstraction entirely (`source_pbx='3cx'`, verified 100%).
- **The four target vendors are deliberately diverse, which is the whole point of the abstraction.** They differ in transport (CUCM = SFTP flat files; Teams = nested Graph REST; Webex/Zoom = flat REST poll; 3CX = raw TCP socket), in correlation key (CUCM `globalCallID`, Teams `callRecord.id`, Webex *Correlation ID*, Zoom `call_uuid`), and in cardinality (Teams/Webex/Zoom emit **multiple legs per logical call**). A "one row per leg, stitched by `correlation_id`" canonical model with a thin per-vendor adapter is the correct foundation — and the columns to support it already exist.
- **The canonical model needs ~10 new columns** (`direction`, `ring_time`, `wait_time`, `hold_time`, `wrap_time`, `abandoned`, `disposition`, `queue_id`, `agent_id`, `currency`) plus `Queue`/`Agent`/`AgentState`/`Disposition`/`Recording`/`CallLeg` models. None of these exist today; every real ACD metric and every cradle-to-grave drill-down depends on them. See [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md) and [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md).
- **The target architecture is event-driven but boring on purpose:** adapters → an ingestion bus (Redis Streams now, Kafka later) → a normalizer (the one place the flagship mixed-case bug is fixed) → the store → async enrichment + rollups → realtime/alerts/API. This decouples the heavy synchronous `CallRecord.save()` (country lookup + regex categorization + costing + quota deduction, all inline on the socket thread) from ingestion.
- **AI/intelligence is a sidecar, not a rewrite.** Transcription, sentiment, anomaly/fraud and forecasting attach to the same event bus and write back to `CallRecord`/`CallLeg`; a natural-language query layer sits in front of the analytics store. Build the data plumbing first; the AI features are cheap to bolt on once the canonical model and bus exist.
- **Two prerequisites block *everything* at scale** and are documented elsewhere: normalize the mixed-case `*_type`/`reason_terminated` tokens at ingest (the bug that silently drops ~half the call-center records — [05](05-Call-Center-Evaluation-Module.md)), and add the missing `(company_id, call_time)` index over 1.49M rows ([04](04-Data-Model-and-Database-Performance.md)). The migration sequencing lives in [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md).

---

## 1. The vendor-neutral vision

### 1.1 Where we are vs where we are going

Today the platform is **structurally single-vendor in practice but multi-vendor in intent**. The intent is real and recent: a 2026-05-12 migration added `source_pbx`/`external_id`/`correlation_id`/`raw_data`, declared eleven `SOURCE_PBX_CHOICES` (`models.py:85-97`), added QoS columns, and committed an adapter scaffold. The reality is that none of it is exercised — the live ingestion path (`socket_server.py`) writes `CallRecord` rows directly and never touches `NormalizedCdr` or `AdapterRegistry`.

| Dimension | Current state | Target state |
|---|---|---|
| Vendors ingested | 1 (3CX), 100% of 1.49M rows | 3CX + Cisco CUCM + Teams + Webex + Zoom + generic SIP |
| Transport | 1 inbound raw TCP socket, auth-less, public | Per-vendor adapters: socket / DB-pull / SFTP / REST-poll, all outbound or authenticated |
| Normalization | None — positional parse straight to ORM | Single `normalize()` step per adapter; one canonical shape |
| Correlation | None — no leg/dedup key captured | `correlation_id` stitches legs of one logical call |
| Tenant resolution | `Company.listening_port == server port` only | Per-adapter: port (3CX socket), org/API credential (cloud), SFTP path (CUCM) |
| Call-center data | Heuristic (`to_type=='Ivr'`, display names) | Real `Queue`/`Agent`/`AgentState`/`Disposition` model |
| Processing | Synchronous, on the socket thread | Event-driven, async enrichment + rollups |

The stakeholder requirement is explicit: the platform must evolve beyond 3CX to also ingest Cisco (CUCM) and other IP telephony across multiple call centers, kept vendor-neutral, with the 3CX San Francisco call center as a priority tenant for call-center evaluation. The market validates this direction — leaders like Variphy and Nectar DXP already span exactly this vendor set (CUCM, UCCX, Webex Calling, Zoom Phone, Teams Phone) from one product, so multi-vendor is table stakes, not differentiation. Our differentiation is *depth* (call-center evaluation, intelligence) on top of the breadth.

### 1.2 Why each vendor is different (and why that's fine)

The four cloud/on-prem targets were researched in detail (see [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md) for 3CX specifics). The summary that drives the design:

| Vendor (`source_pbx`) | Access model | Leg key → `external_id` | Logical-call key → `correlation_id` | QoS source | Notable constraint |
|---|---|---|---|---|---|
| `3cx` | Raw TCP socket (Active CDR) **or** read-only PostgreSQL `cdr_output` (v20 U6) | `cdr_id` (GUID, DB path) / none (socket) | `cdr_id` / call-flow chain | none on socket; `cdr_billing` join in DB | Socket has no dedup key; DB is localhost-only |
| `cisco_cucm` | SFTP flat-file CSV: **CDR** (facts) + **CMR** (media), batched, no realtime | `globalCallID_callId` + `globalCallID_callManagerId` | `globalCallID_callId` | CMR: `VarJitter`, `latency`, `pktsLost`, MLQK/MOS | File-based; join CMR↔CDR by globalCallID |
| `ms_teams` | Graph `callRecords` REST, nested: `callRecord → sessions → segments` | session/segment id | `callRecord.id` | per-segment media stats | Nested graph; flatten each segment to a leg |
| `webex_calling` | Detailed Call History REST (flat, 50+ fields), poll | `Call ID` | **Correlation ID** (first-class) | per-record where available | 5-min delay, ~1 req/min/org, retention shrank 48h→12h — poll often or lose data |
| `zoom_phone` | `GET /phone/call_history` + `Get call path` REST, poll | `call_id` | `call_uuid` | limited | Multi-row journeys; legacy call-log API sunset 2025-11-30 |

The decisive observation: **none of these is a raw TCP socket like 3CX, and three of them emit multiple legs per logical call.** That is precisely why overloading the 3CX socket path is the wrong move and why a "one canonical row per leg, grouped by `correlation_id`" model with a per-vendor adapter is the right one. `raw_data` (jsonb, already present) preserves the untouched vendor payload so any normalization mistake is replayable without re-fetching.

---

## 2. Canonical CallRecord / CallLeg model

### 2.1 The canonical field set

The canonical row is a **superset** that every adapter maps into. Bold rows are **NEW** columns the schema lacks today; everything else already exists on `cdr3cx_callrecord` (verified against `\d cdr3cx_callrecord`).

| Group | Field | Status | Vendor mapping notes |
|---|---|---|---|
| Identity | `id`, `source_pbx`, `external_id`, `correlation_id`, `company_id`, `raw_data` | **Exists** | `external_id` = leg key; `correlation_id` = logical-call key |
| Parties | `caller`, `callee`, `from_dispname`, `to_dispname`, `final_dispname` | Exists | Webex User/User-type, Teams caller/callee |
| Parties | **`caller_name`, `callee_name`, `original_called`, `final_called`** | **NEW** | Redirect target (CUCM `finalCalledPartyNumber`) |
| Routing | **`direction`** (`inbound`/`outbound`/`internal`) | **NEW** | Webex ORIGINATING/TERMINATING; else inferred from normalized `*_type` |
| Timing | `call_time`, `time_answered`, `time_end`, `duration` | Exists | `call_time` = start |
| Timing | **`ring_time`, `wait_time`, `hold_time`, `wrap_time`** (ACW) | **NEW** | wait = `time_answered − call_time`; talk = `time_end − time_answered` |
| Outcome | `reason_terminated` | Exists | **mixed-case — must be normalized** |
| Outcome | **`answered`, `abandoned`, `disposition`, `termination_cause`, `redirect_reason`** | **NEW** | `answered` = `time_answered IS NOT NULL` (cleanest signal — 30.9% are NULL/unanswered) |
| Call-center | **`queue_id`, `queue_name`, `agent_id`, `agent_name`, `site`, `department`, `hunt_group`** | **NEW** | From queue/agent views, not socket |
| QoS | `mos`, `jitter_ms`, `packet_loss_pct`, `latency_ms`, `codec` | Exists (**100% NULL**) | Needs CMR (CUCM) / RTCP-XR / Teams media — not in 3CX socket |
| Billing | `call_category`, `call_rate`, `total_cost` | Exists | See [06-Billing-Quota-and-Fraud.md](06-Billing-Quota-and-Fraud.md) |
| Billing | **`currency`** | **NEW** | `accounts` already has a Currency model (13 rows) but `CallRecord` has no FK |

> Severity/effort note: adding the NEW columns is **High / M** (a migration + adapter wiring); it unblocks the entire ACD metric layer in [05](05-Call-Center-Evaluation-Module.md). The QoS columns existing-but-empty is a separate **Medium / L** workstream (a QoS feed) — do not promise call-quality dashboards until a CMR/RTCP-XR source is ingested.

### 2.2 CallRecord (leg) vs CallLeg / Recording

For depth-of-reporting parity with leaders (Xima Chronicall's "cradle-to-grave" shows every ring/queue/hold/transfer leg), the canonical unit is **the call leg**, and the logical call is reconstructed by grouping on `correlation_id`. Two framings are viable:

- **Flat (recommended first):** one `CallRecord` row per leg, `correlation_id` set, no separate parent table. Simplest, fits the existing table, and is enough for cradle-to-grave drill-down via `ORDER BY call_time WHERE correlation_id = ?`.
- **Parent/child (later):** a thin `Call` parent (one per `correlation_id`) + `CallLeg` children, when per-call rollups (total hold, transfer count) are queried so often that recomputing from legs is wasteful.

Start flat; the `correlation_id` index already exists, so cradle-to-grave is queryable as soon as adapters populate it. A dedicated `Recording` model (file path / post-call URL, linked to the leg) is needed for QA/scorecards — 3CX stores recordings on-box at `/var/lib/3cxpbx/.../Recordings` and the API does not yet expose the filename, so this is a per-vendor capability (see [05](05-Call-Center-Evaluation-Module.md)).

```python
# Indicative additions (see 04 for full DDL + the blocking (company_id, call_time) index)
class CallRecord(models.Model):
    # ... existing vendor-neutral + QoS columns ...
    direction      = models.CharField(max_length=10, null=True, db_index=True)   # inbound/outbound/internal
    ring_time      = models.IntegerField(null=True)   # seconds
    wait_time      = models.IntegerField(null=True)   # queue wait, seconds
    hold_time      = models.IntegerField(null=True)
    wrap_time      = models.IntegerField(null=True)   # ACW
    answered       = models.BooleanField(null=True)
    abandoned      = models.BooleanField(null=True)
    disposition    = models.CharField(max_length=32, null=True)  # canonical: connected/voicemail/no_answer/failed
    queue          = models.ForeignKey('Queue', null=True, on_delete=models.SET_NULL)
    agent          = models.ForeignKey('Agent', null=True, on_delete=models.SET_NULL)
    currency       = models.ForeignKey('accounts.Currency', null=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['source_pbx', 'external_id'],
                                    name='uniq_leg', condition=~Q(external_id=None)),
        ]
        indexes = [models.Index(fields=['company', 'call_time'])]  # the missing index
```

The `UniqueConstraint(source_pbx, external_id)` is what makes re-polling overlapping windows idempotent — the single most important property the socket path lacks today (it has no dedup key at all, so a reconnect/replay would duplicate).

---

## 3. The ingestion adapter contract

### 3.1 What already exists

`cdr3cx/adapters/base.py` is genuinely good and should be **kept and extended, not rewritten**. It provides:

- `NormalizedCdr` — a `@dataclass` carrying identity, parties, timing, routing, geo/cost, QoS and `raw_data`, with `to_call_record_kwargs()` mapping 1:1 to the ORM (`base.py:20-98`).
- `PbxAdapter(ABC)` — declares `source_pbx`, `supports_realtime`, `supports_pull`, an abstract `health_check()`, and optional `fetch_cdrs(since)` (pull) / `handle_event(payload)` (push) methods, plus a `setup_wizard_steps()` hook for a per-tenant UI wizard (`base.py:101-133`).
- `AdapterRegistry` + `@register_adapter` decorator — a process-wide registry keyed by `source_pbx` (`base.py:136-159`).

**Gaps to close:** (1) the registry is empty — there is no `ThreeCXSocketAdapter`, no `ThreeCXDbAdapter`, no cloud adapters; (2) `NormalizedCdr` has no `normalize()`/canonicalization step (it trusts the caller to lowercase `*_type`); (3) it lacks the NEW call-center fields from §2.1; (4) nothing calls it — `socket_server.py` bypasses it.

### 3.2 The target adapter interface

Extend the existing ABC with the four-stage contract the research recommends: **fetch → normalize → correlate → upsert**. The crucial addition is a canonicalization helper so the flagship mixed-case bug is fixed **once, in the ingest layer**, for every vendor:

```python
from cdr3cx.adapters.base import PbxAdapter, NormalizedCdr, register_adapter

# Canonical enums — the ONE place casing is fixed (Ivr/ivr, Extension/extension,
# src_participant_terminated/TerminatedBySrc all collapse here).
def canon_type(v: str | None) -> str | None:
    return v.strip().lower() if v else None   # 'Ivr' -> 'ivr', 'Extension' -> 'extension'

class BaseCDRAdapter(PbxAdapter):
    """Four-stage contract layered on the existing PbxAdapter ABC."""

    def fetch(self, since, until):           # SFTP read / Graph poll / REST poll / socket recv
        raise NotImplementedError

    def normalize(self, raw) -> NormalizedCdr:
        # ALWAYS: store untouched payload in raw_data; canonicalize *_type / reason / disposition.
        raise NotImplementedError

    def correlate(self, records):            # group legs by correlation_id (no-op for single-leg 3CX socket)
        return records

    def upsert(self, records):               # idempotent get_or_create on (source_pbx, external_id)
        for rec in records:
            CallRecord.objects.update_or_create(
                source_pbx=rec.source_pbx, external_id=rec.external_id,
                defaults=rec.to_call_record_kwargs(),
            )
```

A concrete example for the strategic 3CX DB-pull path (the connector recommended in [03](03-CDR-Ingestion-and-3CX-Integration.md)):

```python
@register_adapter
class ThreeCXDbAdapter(BaseCDRAdapter):
    source_pbx, supports_pull, supports_realtime = '3cx', True, False

    def fetch(self, since, until):
        # read-only SELECT on the PBX's cdr_output JOIN cdr_billing, cursor on cdr_started_at
        return self._read_only_query(since, until)

    def normalize(self, row) -> NormalizedCdr:
        return NormalizedCdr(
            source_pbx='3cx',
            external_id=row['cdr_id'], correlation_id=row['cdr_id'],   # GUID = dedup key we lack today
            company_id=self.config['company_id'],
            call_time=row['cdr_started_at'], time_answered=row['cdr_answered_at'],
            time_end=row['cdr_ended_at'],
            from_type=canon_type(row.get('source_type')),
            to_type=canon_type(row.get('destination_type')),
            reason_terminated=canon_type(row.get('termination_reason')),
            raw_data=row,                                               # full vendor JSON preserved
        )
```

The same `BaseCDRAdapter` shape, with a different `fetch()` (SFTP sweep) and `normalize()` (CSV column-name mapping + CMR join), becomes `CiscoCucmAdapter`; with a Graph `$expand=sessions($expand=segments)` poll it becomes `MsTeamsAdapter`; and so on. **All vendor-specific quirks (field order, casing, table/column names, version detection) live inside the adapter; the rest of the system only ever sees `NormalizedCdr`.**

### 3.3 Tenant resolution and scheduling per vendor

| Vendor | Tenant resolution | Runtime | Cadence / limits |
|---|---|---|---|
| 3CX socket | `Company.listening_port == port` (existing) | Hardened socket listener (fallback/real-time tap) | One CDR per connection; loop `recv` until close to fix the 1024-byte truncation |
| 3CX DB | per-tenant read-only DB credential | Scheduled poller | cursor on `cdr_started_at` + `cdr_id` |
| CUCM | SFTP path / billing-server credential | Scheduled file sweep | batch; no realtime exists |
| Teams | Graph app registration (org tenant) | Poller or change-notification subscription | flatten sessions→segments |
| Webex | OAuth `spark-admin:calling_cdr_read` (per org) | Frequent poller | **5-min delay, ~1 req/min, 12–48h retention — poll every few minutes or lose data** |
| Zoom | OAuth `phone:read:...:admin` (per account) | Poller with pagination | multi-row journeys; new `call_history` API |

The cloud adapters require a **real scheduler/worker** — which production does not have today (no Celery, no app cron; only `gunicorn`/`daphne`/`socket_server` in systemd). Standing up that worker is therefore a hard dependency for *any* pull-based vendor (and for scheduled reports and threshold alerts — see [07](07-Reporting-Dashboards-and-UI-UX.md) and [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md)).

---

## 4. Target system architecture (event-driven)

### 4.1 The pipeline

The target is a linear, event-driven pipeline that decouples *receiving* a CDR from *processing* it. Today everything — country lookup (phonenumbers), `categorize_call()` (regex over every `CallPattern`), `calculate_total_cost()`, `update_user_quota()` (DB writes, no `select_for_update`), plus per-record `print()`/`logger.info()` — runs **synchronously inside the socket thread** in `CallRecord.save()`. Worse, saving a `CallPattern` fires `apply_pattern_to_call_records`, which re-saves *all* matching historical rows inline. The target moves all of that off the ingest path.

```
        ┌──────────────────────── INGESTION ADAPTERS ────────────────────────┐
        │ 3CX socket │ 3CX DB pull │ CUCM SFTP │ Teams Graph │ Webex │ Zoom   │
        └──────┬───────────┬────────────┬───────────┬──────────┬──────┬──────┘
               │ fetch + normalize (canonicalize casing, fill raw_data)       │
               └───────────────────────────┬─────────────────────────────────┘
                                            ▼
                          ┌─────────────────────────────────┐
                          │  INGESTION BUS  (Redis Streams   │   one event = one NormalizedCdr
                          │  now → Kafka later)              │   (idempotency key: source_pbx+external_id)
                          └───────────────┬─────────────────┘
                                          ▼
                   ┌──────────────────────────────────────────────┐
                   │  NORMALIZER / VALIDATOR  (single source of    │  ← the ONLY place the mixed-case
                   │  truth for canonical enums + correlation)     │     *_type / reason bug is fixed
                   └───────────────┬──────────────────────────────┘
                                   ▼
                   ┌───────────────────────────┐      ┌──────────────────────────┐
                   │  STORE  (PostgreSQL 16,    │◄────►│  ENRICHMENT WORKERS       │ country lookup,
                   │  partitioned by month,     │      │  (async, idempotent):     │ categorize, cost,
                   │  (company_id, call_time)   │      │  rating, quota (SELECT    │ quota deduction
                   │  index)                    │      │  FOR UPDATE), QoS join    │
                   └───────┬───────────────┬────┘      └──────────────────────────┘
                           ▼               ▼
                 ┌──────────────────┐  ┌──────────────────────┐
                 │ ROLLUPS /        │  │  ANALYTICS / REPORTS  │  pre-aggregated tiles, KPI engine
                 │ MATERIALIZED     │  │  (read models)        │  (replaces 24 per-hour COUNT scans)
                 │ AGG TABLES       │  └──────────┬────────────┘
                 └──────────────────┘             │
        ┌─────────────────────────────────────────┼──────────────────────────────┐
        ▼                          ▼               ▼                ▼              ▼
  REALTIME (Channels/         ALERTS (threshold   PUBLIC API     INTELLIGENCE/   SCHEDULED
  Redis/daphne wallboard)     rules engine)       (DRF+webhooks) AI SIDECAR      REPORTS
```

The bus is the linchpin. With `source_pbx + external_id` as the idempotency key, the pipeline is **at-least-once safe**: re-delivery, re-poll of an overlapping window, or a socket reconnect all resolve to the same `update_or_create`, so no duplicate rows. Each downstream consumer (rollups, alerts, realtime, AI) subscribes independently and can fail/retry without blocking ingestion.

### 4.2 Modular monolith now, services later

This is **not** a microservices proposal. Given two tenants, ~2,000–3,800 calls/day, and one ApiKey with zero webhook deliveries, the operational cost of microservices would dwarf the benefit. The pragmatic path:

| Stage | Shape | Bus | When |
|---|---|---|---|
| Now | Single Django project; adapters as a package; enrichment in a Celery (or RQ) worker against Redis | **Redis Streams** | Stand up the worker; wire `ThreeCXDbAdapter` + harden socket |
| Next | Same monolith; adapters + enrichment + rollups as clearly separated apps with explicit interfaces | Redis Streams | As Teams/Webex/Zoom adapters land |
| Later | Extract the ingestion/normalizer tier and/or analytics read-store *only if* call volume (new high-traffic tenants) or team scaling forces it | **Kafka** | Driven by load, not aspiration |

The architecture is **bus-shaped from day one** so that the later extraction is a deployment change, not a rewrite. Choosing Redis Streams first is deliberate: Redis is already a hard dependency (Channels layer + cache), so it adds zero new infrastructure.

### 4.3 Deployment topology for multi-vendor

A practical wrinkle: 3CX's internal PostgreSQL (`database_single`) is **localhost-only**, and Webex/Zoom retention windows are short. The adapter tier therefore wants to run **close to each data source** — a lightweight per-tenant collector co-located with (or tunneled to) the PBX for DB-pull, and a central scheduler for cloud REST adapters that can reach the public APIs. Collectors push `NormalizedCdr` events to the central bus over an authenticated channel. This also retires the current security liability (an auth-less inbound socket on a public port being probed by `androxgh0st` scanners) — see [09-Security-and-Compliance.md](09-Security-and-Compliance.md).

---

## 5. The intelligence / AI layer

AI attaches to the bus as **independent sidecar consumers** that read events (or the stored leg) and write enrichment back to `CallRecord`/`CallLeg`/`Recording`. Nothing in the core path depends on it, so it can be added incrementally and degrade gracefully.

| Capability | Trigger / input | Output (writes back to) | Build vs adopt |
|---|---|---|---|
| **Transcription** | `Recording` available (post-call URL / file) | `transcript` (new), language | **Adopt** (Whisper API / managed STT); 3CX's own AI tier does this — match it |
| **Sentiment / call summary** | transcript ready | `sentiment`, `summary`, QA signals → scorecards ([05](05-Call-Center-Evaluation-Module.md)) | **Adopt** (LLM API) — cheap to bolt on once transcript exists |
| **Anomaly / fraud** | normalized leg on the bus | `FraudIncident` (18,361 already exist) | **Build** on existing `FraudRule`/`FraudIncident`; move evaluation onto the bus (see [06](06-Billing-Quota-and-Fraud.md)) |
| **Forecasting** | rollup tables (call volume, SLA, occupancy) | capacity/staffing forecasts, WFM inputs | **Build** (statistical baseline) → **adopt** managed forecasting if needed |
| **NL query ("ask your data")** | analytics read-store + schema | text-to-SQL over the canonical model | **Adopt** (LLM + guarded SQL) — only safe *because* the model is canonical and vendor-neutral |

Two design rules make the AI layer tractable:

1. **It consumes the canonical model, not vendor payloads.** Because every vendor normalizes to the same shape, an anomaly detector or NL-query layer written once works across 3CX, CUCM, Teams, Webex and Zoom. This is the compounding payoff of the abstraction.
2. **MOS/QoS is a prerequisite for quality AI, and it's currently empty.** The `mos`/`jitter_ms`/`packet_loss_pct`/`latency_ms` columns are 100% NULL because the 3CX socket carries no QoS. Quality-anomaly and root-cause-isolation features (à la Nectar DXP) need a real QoS feed (CUCM CMR, RTCP-XR, or 3CX Call Quality) before they can do anything — sequence them after a QoS source lands, not before.

> Recommendation: AI features are **strictly downstream of the data-plumbing work**. Resist building any AI feature before the bus, the canonical model, and at least one non-3CX adapter exist — otherwise the AI is trained/run on the same half-missing, mixed-case data that breaks the call-center module today.

---

## 6. Build vs adopt — consolidated decisions

| Concern | Decision | Rationale |
|---|---|---|
| Adapter framework | **Build** (extend existing `adapters/base.py`) | Already scaffolded; vendor mapping is our IP |
| Canonical model | **Build** (extend `CallRecord` + new CC models) | Core domain; must be ours |
| Ingestion bus | **Adopt Redis Streams** now, Kafka later | Redis already deployed; zero new infra |
| Scheduler/worker | **Adopt** Celery (or RQ) | None exists in prod today — hard dependency for cloud adapters, reports, alerts |
| Transcription / STT | **Adopt** managed API | Commodity; not differentiating |
| Sentiment / summary / NL query | **Adopt** LLM API | Commodity; differentiation is in *which* canonical signals we feed it |
| Anomaly / fraud / forecasting | **Build** on existing models, bus-driven | We own the rules and the data |
| Charting / dashboards | **Build** widget layer (see [07](07-Reporting-Dashboards-and-UI-UX.md)) | UX is differentiation; benchmarked vs Variphy/Xima |

---

## 7. Risks and sequencing

| Risk | Severity | Mitigation |
|---|---|---|
| Adapter abstraction stays unused (as today) — features bypass it again | **High** | Make the wired `ThreeCXDbAdapter` the *first* real consumer; delete the direct `CallRecord.create` path in `socket_server.py` once parity is proven |
| Mixed-case normalization not centralized → bug recurs per vendor | **Critical** | `normalize()` is the *only* place casing is fixed; enforce canonical enums at the DB level (CHECK / normalized column) — see [05](05-Call-Center-Evaluation-Module.md) |
| No worker in prod blocks every pull adapter, report, and alert | **High** | Stand up Celery/RQ as the very first infrastructure task ([12](12-Migration-Plan-and-Phased-Roadmap.md)) |
| Sequential scans on 1.49M rows worsen as vendors add volume | **High** | Ship `(company_id, call_time)` index + partitioning **before** onboarding new vendors ([04](04-Data-Model-and-Database-Performance.md)) |
| Vendor API limits (Webex 12h retention) cause silent data loss | **Medium** | Frequent polling + gap detection on `correlation_id`/cursor; alert on missed windows |
| QoS-dependent AI built before a QoS feed exists | **Medium** | Gate quality-AI behind a CMR/RTCP-XR ingestion milestone |

The end-to-end sequencing — worker first, then index/partitioning, then `ThreeCXDbAdapter`, then the canonical-model expansion, then cloud adapters, then the AI sidecar — is specified with milestones, rollback and risk in [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md). KPI definitions that the canonical fields must support are in [13-Call-Center-KPI-and-Metrics-Reference.md](13-Call-Center-KPI-and-Metrics-Reference.md).

---

## 8. Relationship to prior work

The earlier `/home/ubuntu/3CX/enhancement/*.md` set (notably `10-technical-architecture.md`, authored 2026-05-12) framed the multi-vendor ambition as a *business/market* strategy under the "IPT Bill / IPT Insight / IPT Contact" product lines. That framing remains useful for positioning, but for **engineering purposes this document set supersedes it**: the prior docs predate the verification that the adapter scaffold is unused, that QoS columns are 100% empty, that there is no `call_time` index, and that no worker runs in production. The architecture here is grounded in those verified facts rather than aspiration.

---

*Cross-references: [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md) · [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md) · [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md) · [06-Billing-Quota-and-Fraud.md](06-Billing-Quota-and-Fraud.md) · [07-Reporting-Dashboards-and-UI-UX.md](07-Reporting-Dashboards-and-UI-UX.md) · [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md) · [09-Security-and-Compliance.md](09-Security-and-Compliance.md) · [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md) · [13-Call-Center-KPI-and-Metrics-Reference.md](13-Call-Center-KPI-and-Metrics-Reference.md)*
