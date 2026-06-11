# Data Model & Database Performance

This document audits the live data model behind connect.zentryc.com — a single wide `CallRecord` table holding 1,492,192 rows — and defines the schema, indexing, partitioning, and rollup strategy needed to make it correct, fast, and ready for ACD analytics and multi-vendor ingestion. It is evidence-based: every claim is tied to a real column, file line, or query plan captured against the production `cdr` database on 2026-06-05. It pairs each problem with a concrete `current -> target` recommendation and migration-safe DDL.

Sibling documents this one feeds and depends on: ingestion redesign in [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md), the ACD/agent model in [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md), billing/quota correctness in [06-Billing-Quota-and-Fraud.md](06-Billing-Quota-and-Fraud.md), the vendor-neutral adapter target in [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md), KPI formulas in [13-Call-Center-KPI-and-Metrics-Reference.md](13-Call-Center-KPI-and-Metrics-Reference.md), and the phased rollout in [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md).

## TL;DR / Key Takeaways

- **No index on `call_time`.** The 1.49M-row `cdr3cx_callrecord` table is indexed only on `company_id`, `source_pbx`, `external_id`, and `correlation_id` — but essentially every dashboard and report filters by a `call_time` range. A representative monthly count query reads **31,857 buffers (~249 MB) and discards 83,444 rows by filter, taking 315 ms** (EXPLAIN below). This is the single highest-leverage fix in the platform: a `(company_id, call_time DESC)` composite index. **Severity: Critical / Effort: S.**
- **The vendor-neutral columns are 100% empty.** Recent migrations added `external_id`, `correlation_id`, and `raw_data` — but live data shows **0 of 1,492,192 rows populated** for all three. They are schema-only plumbing with no dedup key, no leg correlation, and no preserved source payload. **Severity: High / Effort: M (backfill via re-ingest).**
- **Flagship data-quality bug confirmed in the DB.** `to_type` holds both `Ivr` (112,642) and `ivr` (136,928), and both `Extension` (84,297) and `extension` (67,967). The call-center module filters case-exactly (`Q(to_type='Ivr')`, `final_type='Extension'`), silently dropping roughly half the records — the root cause of the open "call Statics not showing data" complaint.
- **The missed-call filter matches zero rows.** Call-center code filters `reason_terminated='NoAnswer'`, but that literal does not exist in the data; `reason_terminated` is itself mixed-case (`src_participant_terminated` vs `TerminatedBySrc`). The correct, available signal is `time_answered IS NULL` — **461,602 of 1,492,192 calls (30.9%) were never answered.**
- **No ACD entities exist.** There is no `Queue`, `Agent`, `AgentStateEvent`, `Team`, `Disposition`, `CallLeg`, or `Recording` model. Agents and queues are *inferred* heuristically from display names. Every agent-state metric (occupancy, adherence, ACW, true abandonment) is unbuildable until these tables exist.
- **No partitioning or retention policy.** The table grows ~3,000 rows/day across ~22 months (2024-07-31 to 2026-06-05) and is already 500 MB (399 MB heap + 101 MB indexes). Time-range partitioning plus summary rollups are required before multi-vendor ingestion multiplies the volume.

---

## 1. Current schema overview

### 1.1 The `CallRecord` wide table

The entire call-accounting/analytics product runs off one denormalized table, `cdr3cx_callrecord`, defined in [`cdr3cx/models.py:84-281`](file:///home/ubuntu/3CX/cdr/cdr3cx/models.py). It has 36 columns mixing four concerns in one row: raw 3CX socket fields, billing fields, vendor-neutral identity fields, and QoS fields.

| Concern | Columns | Live state (verified 2026-06-05) |
|---|---|---|
| Identity / tenant | `id`, `company_id`, `source_pbx` | 1,492,192 rows; `source_pbx` = `3cx` for 100%; 2 tenants (`Smasco` port 8000, `SAMNAN` port 8005) |
| Vendor-neutral | `external_id`, `correlation_id`, `raw_data` (jsonb) | **0 populated** of 1.49M — pure plumbing |
| 3CX socket fields | `caller`, `callee`, `call_time`, `duration`, `time_answered`, `time_end`, `reason_terminated`, `reason_changed`, `missed_queue_calls`, `from_no`, `to_no`, `to_dn`, `final_number`, `final_dn`, `from_type`, `to_type`, `final_type`, `from_dispname`, `to_dispname`, `final_dispname` | populated; `*_type` fields mixed-case (see §4) |
| QoS | `mos`, `jitter_ms`, `packet_loss_pct`, `latency_ms`, `codec` | **0 populated** — 3CX socket CDR carries no QoS (see [13](13-Call-Center-KPI-and-Metrics-Reference.md)) |
| Billing | `country`, `call_category`, `call_rate`, `total_cost` | 957,203 (64%) have `total_cost = 0`; 34,327 have no `call_category` |

Time span: earliest `call_time` 2024-07-31, latest 2026-06-05 (~22 months). On-disk: **500 MB total** (`pg_total_relation_size`), of which 399 MB is heap and 101 MB is indexes.

### 1.2 Related models and their row counts

| Model (table) | Rows | Role | Reference |
|---|---|---|---|
| `CallPattern` (`cdr3cx_callpattern`) | 11 | regex pattern -> `call_type` -> `rate_per_min` (SAR) | `models.py:20-79` |
| `Quota` / `UserQuota` (`cdr3cx_userquota`) | 779 | per-extension balance; one per Extension | `models.py:285-426` |
| `Extension` (`accounts_extension`) | 779 | telephone extensions; tenant-scoped | `accounts` |
| `Company` (`accounts_company`) | 2 | tenant; resolved by `listening_port` | `accounts` |
| `FraudIncident` (`billing_fraudincident`) | 18,361 | FK `triggering_call_id -> cdr3cx_callrecord` | `billing` |
| `ApiKey` (`api_apikey`) | 1 | public REST API barely used | `api` |

There is a real foreign key from `billing_fraudincident.triggering_call_id` to `cdr3cx_callrecord(id)` — the only inbound FK — which matters for the partitioning plan (§5) and retention (§8).

### 1.3 Heavy synchronous `save()` — a data-model problem, not just a runtime one

`CallRecord.save()` ([`models.py:194-248`](file:///home/ubuntu/3CX/cdr/cdr3cx/models.py)) runs *inside the socket thread* and synchronously performs: a `phonenumbers` country lookup, `categorize_call()` (iterates `company.call_patterns` running regex per row), `calculate_total_cost()`, then `update_user_quota()` (DB writes) — interleaved with ~20 `print()` and `logger.info()` calls *per insert*. Worse, the `apply_pattern_to_call_records` post-save signal ([`models.py:57-79`](file:///home/ubuntu/3CX/cdr/cdr3cx/models.py)) re-saves **all** matching historical records whenever any `CallPattern` is saved — an unbounded synchronous reprocessing loop over up to 1.49M rows, each triggering the full `save()` chain again.

This is relevant to the *data model* because it explains why we cannot simply backfill or re-categorize records cheaply today, and why enrichment (cost, category, quota) must be split out of the ingest write path. The redesign is detailed in [03](03-CDR-Ingestion-and-3CX-Integration.md); here we note only that the model must support a cheap **bulk raw insert** followed by an **idempotent enrichment pass**, which the current `save()` override actively prevents.

---

## 2. Indexing analysis (EXPLAIN-backed)

### 2.1 What indexes exist

From `\d cdr3cx_callrecord`:

```
"cdr3cx_callrecord_pkey"           PRIMARY KEY btree (id)
"cdr3cx_callrecord_company_id_..." btree (company_id)
"cdr3cx_callrecord_source_pbx_..." btree (source_pbx)
"cdr3cx_callrecord_external_id_..." btree (external_id)         -- column 100% NULL
"cdr3cx_callrecord_correlation_id_..." btree (correlation_id)   -- column 100% NULL
```

Two of the five secondary indexes (`external_id`, `correlation_id`, plus their `_like` variants — 4 index objects) cover columns that are **entirely NULL** today. They consume part of the 101 MB index footprint while serving zero queries. There is **no index on `call_time`** and **no composite `(company_id, call_time)`**, despite `Meta.ordering = ['-call_time']` ([`models.py:280-281`](file:///home/ubuntu/3CX/cdr/cdr3cx/models.py)) and every report filtering by a date range.

### 2.2 The cost of the missing index — measured

A representative dashboard query ("how many calls did tenant 1 have last month") on the live DB:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*) FROM cdr3cx_callrecord
WHERE company_id = 1
  AND call_time >= '2026-05-01' AND call_time < '2026-06-01';
```

```
Finalize Aggregate ... (actual time=305.031..314.614 rows=1)
  Buffers: shared hit=3 read=31857
  -> Parallel Bitmap Heap Scan on cdr3cx_callrecord (actual rows=5974)
       Recheck Cond: (company_id = 1)
       Filter: (call_time >= ... AND call_time < ...)
       Rows Removed by Filter: 83444
       Heap Blocks: exact=10920
       Buffers: shared hit=3 read=31857
       -> Bitmap Index Scan on cdr3cx_callrecord_company_id_...
            Index Cond: (company_id = 1)   -- 268,254 rows matched
Execution Time: 314.760 ms
```

The planner uses the only useful index (`company_id`), pulls the **entire 268k-row tenant partition**, then throws away **83,444 rows per worker by post-filter** to find ~18k matches — reading **31,857 8 KB buffers (~249 MB)** for a single tile. The call-center dashboard fires **24 per-hour `COUNT` queries + 21 daily-trend `COUNT` queries** ([`callcenter_views.py`](file:///home/ubuntu/3CX/cdr/cdr3cx/callcenter_views.py)), each repeating a scan of this shape, and `call_back_tracking` runs nested per-number queries in a Python loop (N+1). At 2 tenants this is merely slow; at the multi-vendor volumes in [10](10-Multi-Vendor-and-Target-Architecture.md) it is unusable.

### 2.3 Index recommendations

| # | Recommendation | Rationale | Sev / Effort |
|---|---|---|---|
| I-1 | `CREATE INDEX CONCURRENTLY ... ON cdr3cx_callrecord (company_id, call_time DESC)` | Turns every tenant-scoped date-range scan into an index range scan; also serves `Meta.ordering` | Critical / S |
| I-2 | Partial index for call-center work: `... (company_id, call_time) WHERE final_type IS NOT NULL` once casing is normalized (see §4) | Shrinks the index to call-center-relevant rows | High / S |
| I-3 | BRIN index on `call_time` as a low-cost complement for full-table time scans (rows are append-ordered by time) | ~kilobytes vs MB; great for archival/range sweeps | Medium / S |
| I-4 | Drop the `external_id`/`correlation_id` btree+`_like` indexes **only if** these columns stay NULL; otherwise keep and **populate** them via re-ingest (preferred) | Stop paying for unused indexes, or make them earn their keep | Medium / S |

```sql
-- I-1: the highest-leverage single change in the platform
CREATE INDEX CONCURRENTLY idx_callrecord_company_calltime
    ON cdr3cx_callrecord (company_id, call_time DESC);
```

`CONCURRENTLY` is mandatory: a plain `CREATE INDEX` takes an `ACCESS EXCLUSIVE` lock and would block live socket inserts for the duration of a 1.49M-row build.

---

## 3. Scaling strategy at 1.49M and growing ~3k/day

Linear growth of ~2,000–3,800 rows/day means ~1.1M rows/year *per current tenant pair*. The strategy is three layered moves.

### 3.1 Composite indexes (done in §2) — the immediate win

Ship I-1 first; it removes the 249 MB scan without any schema change or backfill.

### 3.2 Time partitioning — the structural move

Convert `cdr3cx_callrecord` to a **range-partitioned table on `call_time` (monthly partitions)**. Benefits: (a) date-range queries prune to one or two partitions; (b) retention/archival becomes a metadata `DETACH PARTITION` instead of a 22-month `DELETE`; (c) per-partition indexes stay small. PostgreSQL 16 supports declarative partitioning natively.

```sql
-- Target shape (new table; migrate via the swap in §7)
CREATE TABLE callrecord (
    id           bigint GENERATED BY DEFAULT AS IDENTITY,
    company_id   bigint NOT NULL,
    call_time    timestamptz NOT NULL,
    ...           -- all existing columns
    PRIMARY KEY (id, call_time)        -- partition key must be in the PK
) PARTITION BY RANGE (call_time);

CREATE TABLE callrecord_2026_06 PARTITION OF callrecord
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
-- + a monthly create job (see Note on workers below)
CREATE INDEX ON callrecord_2026_06 (company_id, call_time DESC);
```

Two constraints to plan for: the partition key (`call_time`) must be part of every unique/primary key, and the inbound FK from `billing_fraudincident` references `cdr3cx_callrecord(id)` — a partitioned parent supports being referenced in PG 16, but the migration must recreate that FK against the new parent (handled in the §7 ordering).

> **Note on workers:** monthly partition creation, retention detach, and rollup refresh all need a scheduler. Production currently runs **no Celery and no app cron** (only `gunicorn`, `daphne`, `socket_server` under systemd). Until a real worker exists ([12](12-Migration-Plan-and-Phased-Roadmap.md)), use a pre-created buffer of forward partitions and a PostgreSQL-side `pg_cron` extension as a stopgap so the design does not silently stop creating partitions.

### 3.3 Summary / rollup tables and materialized views — the dashboard move

Dashboards must never scan the fact table per tile. Introduce a pre-aggregated hourly rollup that the wallboard and reports read from:

```sql
CREATE TABLE callrecord_hourly_rollup (
    company_id     bigint NOT NULL,
    bucket_hour    timestamptz NOT NULL,        -- date_trunc('hour', call_time)
    queue_id       bigint NULL,
    total_calls    integer NOT NULL DEFAULT 0,
    answered       integer NOT NULL DEFAULT 0,  -- time_answered IS NOT NULL
    abandoned      integer NOT NULL DEFAULT 0,  -- time_answered IS NULL, inbound
    answered_le_sla integer NOT NULL DEFAULT 0, -- within target seconds (for SLA%)
    sum_wait_sec   bigint NOT NULL DEFAULT 0,   -- for ASA
    sum_talk_sec   bigint NOT NULL DEFAULT 0,   -- for AHT (talk component)
    sum_cost       numeric(14,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (company_id, bucket_hour, queue_id)
);
```

This single table replaces the 24+21 per-tile `COUNT` scans with one indexed lookup, and its columns are exactly the building blocks of Service Level, ASA, AHT, and abandonment defined in [13](13-Call-Center-KPI-and-Metrics-Reference.md). Refresh it incrementally on ingest (per inserted batch, `INSERT ... ON CONFLICT DO UPDATE` the affected hour buckets) rather than via a periodic `REFRESH MATERIALIZED VIEW`, so it does not depend on a scheduler. A `MATERIALIZED VIEW` is acceptable for heavier daily/monthly trend reports where minute-level freshness is unnecessary.

| Layer | Backs | Freshness | Sev / Effort |
|---|---|---|---|
| Composite index (I-1) | ad-hoc filtered reads | live | Critical / S |
| Monthly time partitions | range queries, retention | live | High / L |
| Hourly rollup table | dashboards, wallboard tiles, SLA% | per-ingest-batch | High / M |
| Daily/monthly materialized view | long-range trend reports | nightly | Medium / M |

---

## 4. Data-quality issues and normalization

### 4.1 Mixed-case enums — the flagship bug (verified in DB)

```sql
SELECT to_type, count(*) FROM cdr3cx_callrecord
WHERE to_type IN ('Ivr','ivr','Extension','extension') GROUP BY to_type;
--  Extension |  84297
--  Ivr       | 112642
--  extension |  67967
--  ivr       | 136928
```

The same concept exists under two casings. The call-center module filters case-exactly — e.g. `Q(to_type='Ivr')` ([`callcenter_views.py:52`](file:///home/ubuntu/3CX/cdr/cdr3cx/callcenter_views.py)), `final_type='Extension'` ([`callcenter_views.py:68,104,106,107`](file:///home/ubuntu/3CX/cdr/cdr3cx/callcenter_views.py)) — so it **silently excludes the lowercase half**: it counts 112,642 `Ivr` rows but ignores 136,928 `ivr` rows. This is the documented "call Statics not showing data in the table" complaint (`/home/ubuntu/3CX/issues.txt`). The disease extends to `from_type`, `final_type`, and `reason_terminated`.

### 4.2 The broken missed-call filter

The "missed" filter uses `reason_terminated='NoAnswer'` ([`callcenter_views.py:57,105,158,291,363,403`](file:///home/ubuntu/3CX/cdr/cdr3cx/callcenter_views.py)), but **no row contains the literal `NoAnswer`**. Actual top `reason_terminated` values are `src_participant_terminated`, `TerminatedBySrc`, `dst_participant_terminated`, `TerminatedByDst`, `Failed`, `no_route`, `declined`, `not_found`, `timeout`, `busy` — themselves mixed-case duplicates of the same concepts. The reliable, already-available signal is **`time_answered IS NULL`** (461,602 / 1,492,192 = 30.9% never answered). `Failed`/`no_route`/`busy`/`declined` should be classified as *system-disposed*, not customer-abandoned (see [13](13-Call-Center-KPI-and-Metrics-Reference.md)).

### 4.3 Other quality issues

| Issue | Evidence | Target | Sev / Effort |
|---|---|---|---|
| Phone numbers as `varchar(20)`, unnormalized; `recv(1024)` truncates long records | `socket_server.py:31`; `caller/callee/from_no` are `varchar(20)` | normalize to E.164 at ingest; widen to `varchar(32)`; fix ingest framing (see [03](03-CDR-Ingestion-and-3CX-Integration.md)) | High / M |
| `total_cost`/`call_rate` `NOT NULL DEFAULT 0` masks "uncosted" vs "free" | 957,203 rows `total_cost=0` — cannot tell zero-rated from un-rated | make `call_rate` nullable; add `is_rated boolean`; never overload 0 | Medium / M |
| `external_id`/`correlation_id`/`raw_data` 100% NULL | DB count = 0 | populate at ingest; `external_id` = idempotency key; see §6 | High / M |
| No canonical disposition | inferred ad hoc per view | add normalized `call_disposition` enum column | High / M |

### 4.4 Normalization recommendation

Normalize **at ingest** (in the adapter `normalize()` step — [03](03-CDR-Ingestion-and-3CX-Integration.md), [10](10-Multi-Vendor-and-Target-Architecture.md)) into canonical lowercase tokens, and add a **PostgreSQL generated column** as a defense-in-depth bridge for existing data so historical filters work immediately without a full re-ingest:

```sql
ALTER TABLE cdr3cx_callrecord
    ADD COLUMN to_type_norm  varchar(20) GENERATED ALWAYS AS (lower(to_type))  STORED,
    ADD COLUMN final_type_norm varchar(20) GENERATED ALWAYS AS (lower(final_type)) STORED,
    ADD COLUMN answered boolean GENERATED ALWAYS AS (time_answered IS NOT NULL) STORED;

CREATE INDEX idx_callrecord_finaltype_norm
    ON cdr3cx_callrecord (company_id, final_type_norm, call_time DESC);
```

Then every query filters on `final_type_norm = 'extension'` / `to_type_norm = 'ivr'` and `answered`, recovering the silently-dropped half of the data. The generated column is the cheap immediate fix; the durable fix is ingest-time canonicalization so 3CX **and** Cisco feeds land already-normalized.

---

## 5. New entities for ACD + multi-vendor

The current schema has **no** `Queue`, `Agent`, `AgentStateEvent`, `Team`, `Disposition`, `CallLeg`, or `Recording` model. Agents are inferred from `final_dispname`/`final_dn` and queues from `to_dispname ILIKE '%Call Center%'`. That cannot support occupancy, adherence, ACW, true queue-abandonment, QA scorecards, or recordings. The ACD semantics and metric definitions live in [05](05-Call-Center-Evaluation-Module.md) and [13](13-Call-Center-KPI-and-Metrics-Reference.md); here we give the **storage shape**, designed vendor-neutrally so 3CX queue views and Cisco Finesse/CUCM states map onto the same tables ([10](10-Multi-Vendor-and-Target-Architecture.md)).

```python
# cdr3cx/models.py (or a new `acd` app) — model sketches

class Team(models.Model):
    company   = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    name      = models.CharField(max_length=100)
    supervisor = models.ForeignKey('accounts.CustomUser', null=True, on_delete=models.SET_NULL)

class Queue(models.Model):
    company        = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    source_pbx     = models.CharField(max_length=20)           # vendor-neutral
    external_id    = models.CharField(max_length=128)          # 3CX queue DN / CUCM hunt pilot
    name           = models.CharField(max_length=100)
    sla_target_sec = models.PositiveIntegerField(default=20)   # drives Service Level %
    short_abandon_sec = models.PositiveIntegerField(default=10)
    team           = models.ForeignKey(Team, null=True, on_delete=models.SET_NULL)
    class Meta:
        unique_together = ('source_pbx', 'external_id', 'company')

class Agent(models.Model):
    company     = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    extension   = models.ForeignKey('accounts.Extension', null=True, on_delete=models.SET_NULL)
    source_pbx  = models.CharField(max_length=20)
    external_id = models.CharField(max_length=128)             # PBX agent/user id
    display_name = models.CharField(max_length=100)
    team        = models.ForeignKey(Team, null=True, on_delete=models.SET_NULL)

class AgentStateEvent(models.Model):
    STATES = [('logged_out','Logged Out'),('available','Available'),
              ('reserved','Reserved'),('talking','Talking'),
              ('wrap_up','Wrap-Up'),('not_ready','Not Ready')]
    agent      = models.ForeignKey(Agent, on_delete=models.CASCADE)
    state      = models.CharField(max_length=20, choices=STATES)
    reason_code = models.CharField(max_length=40, null=True)   # aux: Break/Lunch/Training
    started_at = models.DateTimeField()
    ended_at   = models.DateTimeField(null=True)               # NULL = current state
    class Meta:
        indexes = [models.Index(fields=['agent','started_at'])]

class Disposition(models.Model):       # wrap/outcome code applied to a call
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    code    = models.CharField(max_length=40)                  # Sale / Callback / Complaint
    is_resolution = models.BooleanField(default=False)         # feeds FCR approximation

class CallLeg(models.Model):           # one logical call -> many legs (transfers/queue)
    call        = models.ForeignKey('CallRecord', on_delete=models.CASCADE, related_name='legs')
    correlation_id = models.CharField(max_length=128, db_index=True)  # stitches legs
    leg_type    = models.CharField(max_length=20)              # inbound/queue/agent/transfer
    queue       = models.ForeignKey(Queue, null=True, on_delete=models.SET_NULL)
    agent       = models.ForeignKey(Agent, null=True, on_delete=models.SET_NULL)
    disposition = models.ForeignKey(Disposition, null=True, on_delete=models.SET_NULL)
    ring_sec    = models.IntegerField(null=True)
    wait_sec    = models.IntegerField(null=True)   # time_answered - call_time
    talk_sec    = models.IntegerField(null=True)
    hold_sec    = models.IntegerField(null=True)
    wrap_sec    = models.IntegerField(null=True)   # ACW — not in 3CX CDR; from AgentState

class Recording(models.Model):
    call        = models.ForeignKey('CallRecord', on_delete=models.CASCADE)
    source_pbx  = models.CharField(max_length=20)
    external_id = models.CharField(max_length=128)
    url         = models.URLField(max_length=500, null=True)   # 3CX recordings table / file path
    duration_sec = models.IntegerField(null=True)
    transcript  = models.TextField(null=True)                  # AI tier (see 10)
```

Additionally, `CallRecord` itself needs the leg-level **derived columns** that every ACD KPI depends on and that the current schema lacks: `direction` (inbound/outbound/internal), `ring_sec`, `wait_sec`, `hold_sec`, `wrap_sec`, `abandoned` (bool), `call_disposition`, plus `queue_id`/`agent_id` FKs and a `currency` field for multi-currency ([06](06-Billing-Quota-and-Fraud.md)). `wait_sec` and `talk_sec` are computable today from `time_answered - call_time` and `time_end - time_answered`; `hold_sec` and `wrap_sec` are **not** in any 3CX CDR and require the `AgentStateEvent` stream ([05](05-Call-Center-Evaluation-Module.md), [13](13-Call-Center-KPI-and-Metrics-Reference.md)).

| New entity | Unlocks | Data source | Sev / Effort |
|---|---|---|---|
| `Queue` (+ `sla_target_sec`) | Service Level %, per-queue SLA, abandonment | 3CX queue views / config | High / M |
| `Agent` | per-agent reports, ownership | 3CX extensions-by-queue view | High / M |
| `AgentStateEvent` | occupancy, adherence, ACW, true abandon | 3CX Call Control API WebSocket | High / L |
| `Disposition` | wrap codes, FCR approximation | agent desktop / API | Medium / M |
| `CallLeg` | cradle-to-grave, transfers, multi-leg | correlation_id stitching | High / L |
| `Recording` | QA scorecards, transcription/sentiment | 3CX recordings table/files | Medium / L |

---

## 6. Idempotency, dedup, and `raw_data`

Today there is **no idempotency key** — one CDR per TCP connection, no `historyid`/`callid`, and `external_id` is NULL — so a reconnect or replay can duplicate rows undetected. Target: every adapter populates `external_id` with the PBX-side unique key and upserts on `(source_pbx, external_id)`:

```python
CallRecord.objects.update_or_create(
    source_pbx=row.source_pbx, external_id=row.external_id,
    defaults={... normalized fields ..., 'raw_data': row.original_payload},
)
```

`raw_data` (jsonb) must hold the untouched vendor payload so records can be re-normalized after a parser fix without re-fetching from the PBX — critical given the positional-parser fragility documented in [03](03-CDR-Ingestion-and-3CX-Integration.md). A partial unique index enforces the contract once columns are populated:

```sql
CREATE UNIQUE INDEX CONCURRENTLY uq_callrecord_source_extid
    ON cdr3cx_callrecord (source_pbx, external_id)
    WHERE external_id IS NOT NULL;
```

---

## 7. Migration-safe DDL ordering

Order matters because of the live socket inserts, the 1.49M-row backfills, and the `billing_fraudincident` FK. Recommended sequence (each step independently shippable; details in [12](12-Migration-Plan-and-Phased-Roadmap.md)):

1. **Indexes, online, zero-downtime first.** `CREATE INDEX CONCURRENTLY idx_callrecord_company_calltime` (I-1). Immediate dashboard relief, no schema change, no lock. *(Critical / S)*
2. **Generated normalization columns** (`to_type_norm`, `final_type_norm`, `answered`) + their index. Then point call-center queries at them and fix the `NoAnswer` filter to `answered = false`. Recovers the dropped half of the data. *(High / S–M)*
3. **Additive nullable columns** on `CallRecord`: `direction`, `ring_sec`, `wait_sec`, `hold_sec`, `wrap_sec`, `abandoned`, `call_disposition`, `currency`, `queue_id`, `agent_id`, `is_rated`. All nullable so they apply instantly to 1.49M rows without a table rewrite. *(High / M)*
4. **New ACD tables** (`Team`, `Queue`, `Agent`, `AgentStateEvent`, `Disposition`, `CallLeg`, `Recording`) — pure `CREATE TABLE`, no impact on existing rows. *(High / L)*
5. **Backfill** `wait_sec`/`talk_sec`/`answered`/`abandoned` from existing timestamps in **batched** updates (e.g. 50k rows per transaction) to avoid long locks and bloat; backfill `external_id`/`correlation_id`/`raw_data` only via re-ingest where the source payload is recoverable. *(High / M)*
6. **Idempotency unique index** `uq_callrecord_source_extid` (partial, `CONCURRENTLY`) once `external_id` is populated by the new ingest path. *(High / S)*
7. **Partitioning swap** (only after the above are stable): create the partitioned `callrecord`, copy in time order, build per-partition indexes, recreate the `billing_fraudincident` FK against the new parent, then atomically `RENAME` the old table out and the new table in within one transaction. Keep the old table as a rollback safety net for one retention cycle. *(High / L)*

The partitioning step is last and reversible by design: until the final rename, all reads/writes stay on the original table.

---

## 8. Data retention and archival

There is **no retention policy** today; the table holds all 22 months and grows forever. With partitioning (§3.2) in place, retention becomes cheap and auditable:

| Tier | Window | Storage | Mechanism |
|---|---|---|---|
| Hot | 0–13 months | partitioned `callrecord`, full indexes | live |
| Warm | 13–36 months | older partitions, BRIN-only, optionally `pg_repack`/compressed tablespace | `DETACH PARTITION` -> attach to archive schema |
| Cold | > 36 months | exported Parquet/CSV to object storage; row deleted from PG | scheduled export then `DROP PARTITION` |

Two dependencies: (1) the `billing_fraudincident` FK means fraud incidents referencing archived calls must be re-pointed or denormalized before a partition is dropped; (2) any regulatory retention requirement (call-recording and PII rules, MENA data residency) is governed by [09-Security-and-Compliance.md](09-Security-and-Compliance.md) — the partition windows above must be reconciled with the legal retention period defined there before any `DROP`. Because no worker/cron runs in production, the detach/export/drop jobs must be scheduled on the new worker introduced in [12](12-Migration-Plan-and-Phased-Roadmap.md), not assumed.

---

## 9. Consolidated findings & recommendations

| ID | Finding | Recommendation (current -> target) | Sev | Effort |
|---|---|---|---|---|
| DM-1 | No `call_time` index; 249 MB scan per dashboard tile | seq/bitmap scan -> `(company_id, call_time DESC)` index | Critical | S |
| DM-2 | `*_type` mixed casing drops ~half the rows; `NoAnswer` filter matches 0 | case-exact filters -> normalized columns + `answered` flag | Critical | M |
| DM-3 | `external_id`/`correlation_id`/`raw_data` 100% NULL; no dedup | no idempotency -> upsert on `(source_pbx, external_id)` + raw payload | High | M |
| DM-4 | No `Queue`/`Agent`/`AgentStateEvent`/`CallLeg`/`Recording` | heuristic inference -> first-class ACD model layer | High | L |
| DM-5 | 1.49M rows, ~3k/day, no partitioning/retention | single growing table -> monthly partitions + tiered retention | High | L |
| DM-6 | Dashboards run 24+21 `COUNT` scans + N+1 loop | per-tile fact scans -> hourly rollup table | High | M |
| DM-7 | `total_cost` 0 conflates free vs un-rated (957k rows) | overloaded 0 -> nullable rate + `is_rated` flag | Medium | M |
| DM-8 | Heavy synchronous `save()` blocks ingest; unbounded re-save signal | inline enrich -> bulk raw insert + idempotent enrichment pass (see [03](03-CDR-Ingestion-and-3CX-Integration.md)) | High | M |
| DM-9 | Two indexes on permanently-NULL columns | unused indexes -> populate columns or drop indexes | Medium | S |

The single most valuable next action is **DM-1 followed by DM-2** — together they make the existing dashboards both fast and correct in days, with no risky schema rewrite, and directly close the open "call Statics not showing data" complaint. Everything else builds toward the ACD model in [05](05-Call-Center-Evaluation-Module.md) and the multi-vendor target in [10](10-Multi-Vendor-and-Target-Architecture.md), sequenced in [12](12-Migration-Plan-and-Phased-Roadmap.md).
