# Call Center Evaluation Module (Priority)

This is the flagship engineering specification for turning the connect.zentryc.com portal from a call-accounting tool with a cosmetic "call-center" tab into a credible Automatic Call Distributor (ACD) analytics and agent/supervisor-evaluation product. It documents exactly why the current module silently under-reports (with verified row counts), defines a vendor-neutral ACD data model, specifies the full agent and supervisor KPI suite with formulas and CDR field mappings, gives concrete dashboard/wallboard and QA-scorecard designs, and sets a phased build order anchored on the priority **3CX San Francisco** call-center tenant.

This document is the engineering source of truth for the call-center module. It supersedes the call-center sections of the older `/home/ubuntu/3CX/enhancement` business-strategy set for build purposes. Sibling docs are linked rather than restated: data model and indexing in [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md), ingestion options in [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md), realtime/alerts in [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md), dashboard UX in [07-Reporting-Dashboards-and-UI-UX.md](07-Reporting-Dashboards-and-UI-UX.md), multi-vendor target architecture in [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md), and **precise KPI formula derivations in [13-Call-Center-KPI-and-Metrics-Reference.md](13-Call-Center-KPI-and-Metrics-Reference.md)**.

## TL;DR / Key Takeaways

- **The module silently drops 50-75% of its data.** Filters use exact case (`Q(to_type='Ivr')`, `final_type='Extension'`) but production data is mixed-case. Verified on the live 1,492,192-row table: `to_type='Ivr'` matches **112,642** rows vs **249,570** case-insensitively (55% lost); `final_type='Extension'` matches **37,603** vs **147,702** (75% lost). This is the root cause of the open complaint in `/home/ubuntu/3CX/issues.txt` ("why the call Statics not showing data in the table").
- **The "missed call" filter matches ZERO rows.** `Q(reason_terminated='NoAnswer')` appears at `callcenter_views.py:57,105,158,291,363,403` — but the literal `NoAnswer` does **not exist** in the data (verified: 0 rows). Real values are `src_participant_terminated`, `TerminatedBySrc`, etc. The correct, reliable answered/unanswered signal is `time_answered IS NULL` (461,602 / 1,492,192 = **30.9%** unanswered).
- **There are no real ACD metrics.** No Service Level, ASA, AHT, ACW, occupancy, adherence, true abandonment, FCR, or longest-wait. Agents and queues are *inferred* from `to_type=='Ivr'` and display-name guessing — there is no `Queue`, `Agent`, `AgentState`, `Disposition`, or `Recording` model.
- **The dashboard is unindexed and O(n) per tile.** `call_center_dashboard` runs 24 per-hour COUNT queries (`callcenter_views.py:137-144`) + 7×3 daily-trend COUNTs, each a scan over 1.49M rows with **no index on `call_time`** (verified: indexes exist only on `company_id`, `source_pbx`, `external_id`, `correlation_id`). `call_back_tracking` runs nested per-number queries in a Python loop (N+1, hundreds of queries).
- **What CDR can deliver today (after fixes):** Service Level, ASA, Abandonment (+ short-abandon), Average Wait, Answered%, talk-time handle time — all derivable from existing `call_time` / `time_answered` / `time_end` / `duration` columns.
- **What CDR cannot deliver — needs a new agent-state layer:** Occupancy, Utilization, Adherence, true ACW/wrap, hold time, Aux/Not-Ready codes, agent Available/On-Call/Wrap states. **What needs separate feeds:** MOS/QoS (columns exist but are 100% NULL), CSAT/NPS (survey subsystem), true FCR (CRM linkage), QA (recordings + scorecards).
- **Build order:** (P0) fix casing + missed-call logic + add `(company_id, call_time)` index; (P1) corrected SL/ASA/Abandon/Wait reporting + role-based dashboards; (P2) live supervisor wallboard via Call Control API; (P3) agent-state layer; (P4) survey CSAT/FCR + QA scorecards; (P5) QoS/MOS ingestion. Keep every model vendor-neutral for the planned Cisco CUCM expansion.

---

## 1. What Exists Today, and Why It Under-Reports

The module lives in `cdr3cx/callcenter_views.py` (545 lines) with templates `templates/cdr/callcenter/{dashboard,agent_details,missed_calls,call_back_tracking}.html`. It has three structural defects: a data-quality bug that hides most data, heuristic call-center identification, and a query pattern that does not scale.

### 1.1 The flagship data-quality bug: case-sensitive filters on mixed-case data

Every "call-center call" is identified by an exact-case filter (`callcenter_views.py:52`):

```python
.filter(Q(to_type='Ivr') | Q(final_type='Ivr') | Q(to_dispname__icontains='Call Center'))
```

and "answered by an agent" by `final_type='Extension'` (`callcenter_views.py:68, 104, 161`). Production data is mixed-case — the raw 3CX feed emits both title-case (`Ivr`, `Extension`) and lowercase (`ivr`, `extension`) tokens for the same concept. Verified against the live `cdr` database on 2026-06-05:

| Filter in code | path:line | Rows matched (exact) | Rows matched (case-insensitive) | Records silently dropped |
|---|---|---:|---:|---:|
| `to_type='Ivr'` | `callcenter_views.py:52` | 112,642 | 249,570 | **136,928 (55%)** |
| `final_type='Extension'` | `callcenter_views.py:68,104` | 37,603 | 147,702 | **110,099 (75%)** |
| `reason_terminated='NoAnswer'` | `callcenter_views.py:57,105,158,291,363,403` | **0** | 27 (substring) | **all 461k true misses missed** |

The "answered by agent" path loses three out of four matching records, and the "missed" predicate matches literally nothing. The dashboard therefore shows a near-empty table — exactly the complaint logged in `/home/ubuntu/3CX/issues.txt`. The same disease affects `reason_terminated`, whose top real values are `src_participant_terminated` (494,775), `TerminatedBySrc` (301,009), `dst_participant_terminated` (216,793), `TerminatedByDst` (161,553), `Failed` (161,079) — note the mixed-case duplicates (`src_participant_terminated` vs `TerminatedBySrc`).

**Current → Target.** Replace every `reason_terminated=='NoAnswer'` test with the reliable signal **`time_answered IS NULL`** (a real `timestamptz` column; NULL = never answered; 461,602 rows = 30.9%). Normalize all `*_type` and `reason_terminated` comparisons case-insensitively, and — better — canonicalize at ingest into a lowercase enum plus a derived `call_disposition` column. Casing normalization is owned by the ingestion layer; see [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md) and [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md). A correct interim filter:

```python
from django.db.models.functions import Lower
cc = (CallRecord.objects
      .filter(company=company, call_time__range=(start, end))
      .annotate(tt=Lower('to_type'), ft=Lower('final_type'))
      .filter(Q(tt='ivr') | Q(ft='ivr') | Q(to_dispname__icontains='call center')))
answered   = cc.filter(time_answered__isnull=False)
unanswered = cc.filter(time_answered__isnull=True)
```

### 1.2 Heuristic IVR/agent detection is not a call-center model

"Call-center calls" = `to_type/final_type == Ivr` OR `to_dispname` contains "Call Center"; "agents" are inferred from `final_dispname`/`final_dn`. There is no notion of a **queue**, an **agent roster**, queue membership, or which calls were truly *offered to a queue* versus an IVR auto-attendant. A 3CX IVR (auto-attendant) and an ACD **queue** are different objects; conflating them inflates "call-center" volume with menu navigation and produces the misleadingly low ASA we observed in sampling (avg `time_answered - call_time` of 0.2s over IVR-tagged calls — IVR legs auto-"answer" instantly). Real queue/agent membership exists in the 3CX database views `callcent_queuecalls_view` and `extensions_by_queues_view`, reachable only via the DB-pull path discussed in [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md) — not the socket feed.

### 1.3 Query performance: unindexed full scans and N+1 loops

There is **no index on `call_time`** and no composite `(company_id, call_time)` index, yet every view filters by a `call_time` range. `EXPLAIN` of a one-month company query shows a bitmap scan on `company_id` only, then a recheck across all of that tenant's rows — for the larger tenant that is hundreds of thousands of rows per tile. The dashboard compounds this:

- `callcenter_views.py:137-144` — a Python `for hour in range(24)` loop issuing **24 separate `COUNT`** queries.
- `callcenter_views.py:147-170` — 7 days × 3 counts = **21 more** filtered COUNTs.
- `callcenter_views.py:394-465` — `call_back_tracking` loops over up to 100 numbers, each running 2-3 fresh `CallRecord` queries (**N+1**, hundreds of queries per page load).

| Issue | Evidence | Severity | Effort | Recommendation |
|---|---|---|---|---|
| Case-sensitive `*_type` filters drop 55-75% of data | `callcenter_views.py:52,68,104` + DB counts | **Critical** | S | Normalize case at ingest + `Lower()` in queries |
| `reason_terminated='NoAnswer'` matches 0 rows | `callcenter_views.py:57,105,158,291,363,403` | **Critical** | S | Use `time_answered IS NULL`; classify Failed/no_route/busy separately |
| No `call_time` index → seq/bitmap scans on 1.49M rows | `pg_indexes`; `EXPLAIN` | **Critical** | S | Add `(company_id, call_time)` index (see doc 04) |
| 24 per-hour + 21 daily COUNT queries per dashboard | `callcenter_views.py:137-170` | High | M | Single `GROUP BY date_trunc('hour'...)` aggregate |
| N+1 in `call_back_tracking` | `callcenter_views.py:394-465` | High | M | Set-based window query; pre-join callbacks |
| No real ACD metrics (SL/ASA/AHT/abandon) | entire module | **Critical** | L | Build KPI layer (Section 3) |
| IVR ≠ Queue conflation | `callcenter_views.py:52` | High | M | Introduce `Queue`/`Agent` models (Section 2) |

A single grouped query replaces all 45 hourly/daily COUNTs:

```python
from django.db.models.functions import TruncHour
hourly = (cc.annotate(h=TruncHour('call_time'))
            .values('h')
            .annotate(total=Count('id'),
                      answered=Count('id', filter=Q(time_answered__isnull=False)))
            .order_by('h'))
```

---

## 2. A Proper ACD Data Model

The current schema has vendor-neutral CDR columns (`source_pbx`, `external_id`, `correlation_id`, `raw_data`, QoS fields, `call_category`, `call_rate`, `total_cost`) but **no** `Queue`, `Agent`, `AgentState`, `Team`, `Disposition`, `Recording`, or `CallLeg` entities, and `CallRecord` has no `direction`, `ring_time`, `wait_time`, `hold_time`, `wrap_time`, or `abandoned` flag. Those absences are precisely what block real agent/queue metrics. The full DDL and migration/partitioning strategy belong to [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md); here we define the *contact-center* entities and their semantics.

### 2.1 Entities

```python
class Queue(models.Model):
    company    = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    source_pbx = models.CharField(max_length=32)          # '3cx', 'cucm', ...
    external_id = models.CharField(max_length=128)        # vendor queue id/DN
    name        = models.CharField(max_length=128)
    sla_target_seconds   = models.PositiveIntegerField(default=20)   # SL = X/Y
    sla_target_pct       = models.PositiveIntegerField(default=80)
    short_abandon_seconds = models.PositiveIntegerField(default=10)
    class Meta:
        unique_together = ('company', 'source_pbx', 'external_id')

class Agent(models.Model):
    company    = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    extension  = models.ForeignKey('accounts.Extension', null=True, on_delete=models.SET_NULL)
    source_pbx = models.CharField(max_length=32)
    external_id = models.CharField(max_length=128)        # agent/DN id at the PBX
    display_name = models.CharField(max_length=128)
    queues     = models.ManyToManyField(Queue, through='QueueMembership')

class AgentState(models.Model):                            # event-sourced presence
    AVAILABLE='available'; RESERVED='reserved'; ON_CALL='on_call'
    WRAP='wrap'; NOT_READY='not_ready'; OFFLINE='offline'
    agent      = models.ForeignKey(Agent, on_delete=models.CASCADE)
    state      = models.CharField(max_length=16)
    reason_code = models.CharField(max_length=32, blank=True)  # Break/Lunch/Training...
    started_at = models.DateTimeField(db_index=True)
    ended_at   = models.DateTimeField(null=True)              # NULL = current state

class Disposition(models.Model):                           # wrap/outcome codes
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    code    = models.CharField(max_length=32)              # 'sale','callback','no_answer'
    label   = models.CharField(max_length=64)
    is_resolution = models.BooleanField(default=False)     # feeds operational FCR

class Recording(models.Model):
    call      = models.ForeignKey('CallRecord', on_delete=models.CASCADE)
    storage_url = models.CharField(max_length=512)
    transcript = models.TextField(blank=True)
    sentiment  = models.FloatField(null=True)
```

`CallRecord` gains the ACD columns it lacks: `direction` (inbound/outbound/internal, inferred from normalized `from_type` vs `to_type`/`final_type` — `provider`/`line` on the from-side = inbound external), `ring_time`, `wait_time`, `hold_time`, `wrap_time`, `abandoned` (bool), `disposition` (FK), `queue` (FK), `agent` (FK). Wait and talk are derivable today: `wait = time_answered − call_time`, `talk = time_end − time_answered` (or the existing `duration` int).

### 2.2 How to populate it from 3CX

Three feeds map onto these models with very different fidelity (full transport analysis in [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md)):

| Model / field | Best 3CX source | Available now? |
|---|---|---|
| `CallRecord` wait/talk/answered/abandoned | Socket CDR `call_time`/`time_answered`/`time_end` (after casing fix + index) | **Yes** |
| `Queue`, `Agent`, queue membership, ring/poll attempts | DB views `callcent_queuecalls_view`, `extensions_by_queues_view` (read-only DB pull, v20 U6 `cdr_output`) | Yes, via DB connector |
| `AgentState` (Available/Wrap/Not-Ready), Aux codes | 3CX **Call Control API** WebSocket (participant state events); on-box, edition-gated | New work |
| `Disposition`/wrap codes | Agent desktop / Call Control; 3CX has **no native ACW** | New work |
| `Recording` URL + transcript | 3CX `recordings` table + files at `/var/lib/3cxpbx/...` (API does not expose filename yet); transcript needs AI tier | New work |

The agent-state and disposition models are populated by an **event stream**, not by CDR mining — that is the whole point. Critically, 3CX itself provides **no** agent-controlled wrap-up/ACW, occupancy, adherence, or FCR (3CX docs: agents "log out to do paperwork"), so these are differentiators we build, not data we receive.

---

## 3. KPI Suite — Agent and Supervisor Evaluation

Every metric below is defined here with its formula and the source CDR fields; the deep derivations, edge cases (denominator choices, short-abandon handling, E-model MOS), and benchmark targets live in **[13-Call-Center-KPI-and-Metrics-Reference.md](13-Call-Center-KPI-and-Metrics-Reference.md)**. The columns "Source" and "Buildable now?" are the load-bearing engineering facts.

### 3.1 Operational / queue & supervisor KPIs

| KPI | Formula (summary) | Source fields | Buildable now? |
|---|---|---|---|
| **Service Level (X/Y, e.g. 80/20)** | answered within target ÷ (answered + abandoned) × 100 | `time_answered − call_time ≤ Queue.sla_target_seconds` | **Yes** (+ per-queue SLA config) |
| **ASA** (Avg Speed of Answer) | Σ(wait of answered) ÷ answered | `AVG(time_answered − call_time)` where answered | **Yes** |
| **Abandonment Rate** | abandoned ÷ inbound offered × 100 | `time_answered IS NULL` on inbound queue calls | **Yes** |
| **Short-abandon** (exclude misdials) | abandons where `time_end − call_time ≤ short_abandon_seconds` | `Queue.short_abandon_seconds` | **Yes** |
| **Average / Longest Wait (historical)** | avg/max wait before answer or abandon | `time_answered − call_time` / `time_end − call_time` | **Yes** |
| **Longest Wait (live, oldest in queue)** | age of oldest currently-waiting caller | **live queue state** (Call Control API) | **No — realtime feed** |
| **Calls Waiting / Agents Available (live)** | live counters | live queue/agent feed | **No — realtime feed** |
| **Occupancy** | (talk+hold+ACW) ÷ (talk+hold+ACW+idle) × 100 | **`AgentState` stream** | **No — agent-state layer** |
| **Utilization** | (handle+ACW) ÷ total logged-in shift × 100 | `AgentState` + WFM schedule | **No — WFM** |
| **Schedule Adherence** | minutes in adherence ÷ scheduled minutes × 100 | `Schedule` + `AgentState` | **No — WFM** |

**Caution on abandonment:** `time_answered IS NULL` also covers system-disposed `Failed`/`no_route`/`busy`/`declined` outcomes. These must be classified **separately** (system-disposed vs customer-abandoned) so abandonment is not overstated — drive the classification off normalized `reason_terminated`.

### 3.2 Agent productivity & quality KPIs

| KPI | Formula (summary) | Source | Buildable now? |
|---|---|---|---|
| **Handle Time (talk)** | `time_end − time_answered` (or `duration`) | CDR | **Yes** (label "talk", not "AHT") |
| **AHT (full)** | (talk + hold + ACW) ÷ handled | needs hold + ACW | **No — agent-state** |
| **ACW / Wrap** | wrap time ÷ calls | `AgentState` wrap intervals | **No — agent-state** |
| **Calls Handled / Transfer Rate** | counts | CDR (transfers need leg correlation) | Partial |
| **Operational FCR (approx)** | 1 − (repeat callers within window ÷ contacts) | repeat `from_no` within 24-72h, same queue | Approx, **caveated** |
| **True FCR** | resolved-first-contact ÷ total | CRM case linkage + survey | **No — CRM/survey** |
| **CSAT / CES / NPS** | top-box ÷ responses; etc. | **post-call survey** subsystem | **No — survey** |
| **QA Score** | weighted scorecard, critical auto-fails | `Evaluation` model + recording | **No — QA module (Sec 5)** |
| **MOS** (voice quality) | device-reported, or ITU-T G.107 E-model R-factor | QoS feed (RTCP-XR / 3CX Call Quality) | **No — columns 100% NULL** |

> **MOS reality check:** `mos`, `jitter_ms`, `packet_loss_pct`, `latency_ms` exist on `CallRecord` but are **100% NULL** (0 of 1.49M). Socket CDR carries no QoS. A "call quality" dashboard is empty until a QoS feed is ingested — a separate workstream, not a query change.

A balanced **agent scorecard** combines productivity (handle time, calls handled), quality (QA score, CSAT), and adherence/occupancy once the agent-state layer exists — never productivity alone.

---

## 4. Dashboard & Wallboard Designs

Per wallboard UX research, each view shows only **4-6 behaviour-changing metrics**, each **paired with its target** and colour-coded green/amber/red against the *configured* `Queue.sla_target_*`/threshold values — not platform defaults. Build **three role-based views**. Charting, drag-drop widgets, dark mode, and exports are specified in [07-Reporting-Dashboards-and-UI-UX.md](07-Reporting-Dashboards-and-UI-UX.md); the realtime transport (Channels/Redis/daphne) and alert plumbing in [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md).

### 4.1 Supervisor real-time wallboard (live feed — not the CDR table)

The CDR is written only at call end and has no live queue state; the wallboard **must** be driven by a live 3CX Call Control/Queue feed pushed over the existing Channels/Redis/daphne path.

```
+---------------------------------------------------------------------------+
|  SAN FRANCISCO CALL CENTER — Sales Queue        Service Level (80/20)     |
|  Calls Waiting:  4        Longest Wait: 02:14 [AMBER >90s]    NOW: 76% [R] |
+----------------------------+----------------------------+-----------------+
|  ASA (today)   00:31 [A]   |  Abandon % today  6.2% [R] |  Offered  482   |
|  Handled 451   Aband 31    |  Target ASA <25s           |  In SLA   343   |
+----------------------------+----------------------------+-----------------+
|  AGENTS (12)   Available 3  On-Call 6  Wrap 2  Not-Ready 1  Offline 0     |
|  ----------------------------------------------------------------------   |
|   Maria R.   On-Call  04:12   |  Ahmed K.  Wrap   00:48  | Lin T. Avail   |
|   Jose P.    On-Call  01:03   |  Sara M.   NotRdy(Lunch) | ...            |
|   [ Monitor ] [ Whisper ] [ Barge ]  <- Call Control actions (Sec 6)      |
+---------------------------------------------------------------------------+
```

`Monitor/Whisper/Barge` are call-control actions (Call Control API), distinct from analytics — they deliver the "supervisor evaluation" capability and are gated on PRO/on-box tenants.

### 4.2 Agent self-service dashboard (personal/coaching)

```
+--------------------------- MY PERFORMANCE — Maria R. ---------------------+
|  Today: Calls Handled 38   Talk Time avg 03:41   Wrap avg 00:52           |
|  +-------------------+  +-------------------+  +-----------------------+   |
|  | QA Score   88%  G |  | CSAT      4.4/5 G |  | FCR (approx) 71%  A  |   |
|  | target >85%       |  | target >4.2      |  | target >75%         |   |
|  +-------------------+  +-------------------+  +-----------------------+   |
|  Occupancy 82% [G]  (target 70-90%)     Adherence 94% [G]                 |
|  Recent coaching note: "Confirm callback number before closing."          |
+--------------------------------------------------------------------------+
```

Occupancy/Adherence tiles render only once the agent-state layer exists; until then they show "Not yet available" rather than fabricated numbers. A **Manager** view (trends, SL attainment over time, occupancy, forecast vs actual) is the third role and is largely the report catalogue in [07-Reporting-Dashboards-and-UI-UX.md](07-Reporting-Dashboards-and-UI-UX.md).

### 4.3 Cradle-to-grave drill-down

Mature competitors (e.g. Xima Chronicall) let a supervisor expand any call to see every ring/queue/hold/transfer/agent leg. With `CallLeg`/`correlation_id` stitching (doc 04/10), the agent and call-back views become true call-journey timelines rather than single-row guesses.

---

## 5. QA / Scorecard & Evaluation Workflow

Quality evaluation is a net-new subsystem and the heart of "agent + supervisor evaluation." Methodology (score every interaction where possible; weighted criteria with behavioural definitions; critical/auto-fail items; quarterly scorecard review; agent involvement for buy-in) follows ICMI/Calabrio practice.

```python
class Scorecard(models.Model):
    company = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    name    = models.CharField(max_length=128)
    version = models.PositiveIntegerField(default=1)

class ScorecardItem(models.Model):
    scorecard = models.ForeignKey(Scorecard, related_name='items', on_delete=models.CASCADE)
    criterion = models.CharField(max_length=256)     # e.g. "Verified caller identity"
    weight    = models.PositiveIntegerField()
    auto_fail = models.BooleanField(default=False)   # compliance breach -> 0 overall

class Evaluation(models.Model):
    call      = models.ForeignKey('CallRecord', on_delete=models.CASCADE)
    agent     = models.ForeignKey(Agent, on_delete=models.CASCADE)
    evaluator = models.ForeignKey('accounts.CustomUser', on_delete=models.PROTECT)
    scorecard = models.ForeignKey(Scorecard, on_delete=models.PROTECT)
    total_score = models.DecimalField(max_digits=5, decimal_places=2)
    coaching_note = models.TextField(blank=True)

class Calibration(models.Model):                     # same call, many graders
    call      = models.ForeignKey('CallRecord', on_delete=models.CASCADE)
    evaluations = models.ManyToManyField(Evaluation)
    variance  = models.FloatField(null=True)         # inter-rater spread
```

**Workflow:** (1) supervisor or sampling rule selects calls (link `Recording` + transcript); (2) evaluator grades against the active `Scorecard`, auto-fail items zero the call; (3) score writes back to the agent and feeds the agent scorecard alongside CSAT and operational KPIs; (4) **calibration** sessions have multiple evaluators grade the same call, and the tool surfaces inter-rater **variance** to remove evaluator bias; (5) scores become coaching notes, not just measurement. QA depends on `Recording` (no `recording_url` today) and ideally transcript/sentiment (3CX AI tier or external STT).

---

## 6. Alerting & Escalation for SLA Breaches and Abandonment Spikes

The same `Queue` threshold config that colours wallboard tiles must drive alerts — one **ThresholdPolicy**, three consumers (formula parameterization, wallboard colour, alert/escalation). Alert *early* (amber) so supervisors intervene before SL breaks (red).

| Trigger | Condition | Action | Channel |
|---|---|---|---|
| Longest wait | oldest caller > `wait_warn_seconds` | notify supervisor of queue | Channels push + email |
| SL trending down | rolling SL < `sla_target_pct` − margin | amber banner, supervisor ping | Channels |
| Abandon spike | abandon% over window > threshold | escalate to manager; suggest reroute | email + WhatsApp |
| Agent stuck in Wrap | wrap > `max_wrap_seconds` | nudge agent + flag supervisor | Channels |

**Production reality (must fix before promising "rich alerts"):** there is **no Celery and no app cron actually running** (only gunicorn/daphne/socket_server). Any "scheduled" alert will not fire. Two viable runtimes: (a) evaluate thresholds **on-ingest / in the realtime consumer** for live triggers; (b) run a **real worker** for windowed/escalation alerts. Also, recipient routing is broken: `UserQuota.send_quota_alert()` **hardcodes `recipient='khuram2025@gmail.com'`** (a developer address) — escalations must resolve to the actual queue/supervisor owner. Full alert-rules engine, escalation tiers, and channel integration are specified in [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md).

---

## 7. Pilot: 3CX San Francisco, and Generalizing to Multi-Vendor

The **3CX San Francisco** call center is the priority evaluation tenant. It is the ideal pilot because every capability above can be proven there and then generalized. Two data paths run in parallel:

- **Historical reporting** from the CDR (Service Level, ASA, Abandonment, Average Wait, talk-time AHT, trends) — batch, indexed, aggregated. *Available immediately after the P0 fixes.*
- **Real-time wallboard** from a live 3CX Call Control/Queue feed over Channels/Redis/daphne (calls waiting, longest/oldest wait, agent states, live SL, Monitor/Whisper/Barge). *Requires the Call Control connector.*

Every model in Sections 2 and 5 is deliberately **vendor-neutral**: `Queue`/`Agent`/`AgentState`/`Disposition`/`Recording` are keyed on `(source_pbx, external_id)`, and the agent-state enum is defined to map onto Cisco Finesse and Webex states as cleanly as onto 3CX Call Control. When Cisco CUCM (CDR/CMR SFTP files), MS Teams (Graph `callRecords`), Webex (Correlation-ID CDRs), and Zoom Phone are added, their queue/agent/state feeds populate the **same** tables and the **same** KPI engine computes identical metrics. The adapter pattern and per-vendor identifier mapping are owned by [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md). The intent — "evolve beyond 3CX to ingest Cisco CUCM and other IP telephony + multiple call centers" — is satisfied by building the model layer vendor-neutral from day one, not retrofitting it later.

---

## 8. Phased Build Order

| Phase | Scope | Key deliverables | Depends on | Effort |
|---|---|---|---|---|
| **P0 — Stop the bleeding** | Data-quality + perf | Case-insensitive/normalized filters; replace `NoAnswer` with `time_answered IS NULL`; add `(company_id, call_time)` index; collapse 45 COUNTs into grouped queries; fix `call_back_tracking` N+1 | doc 04 (index/normalization) | **S** |
| **P1 — Real ACD reporting** | KPI engine on CDR | Service Level (per-queue SLA config), ASA, Abandonment (+short-abandon), Avg/Longest Wait, Answered%, talk-time AHT; `Queue`/`Agent` models + membership from DB views; role-based Supervisor/Agent/Manager dashboards (target-paired, colour-coded) | doc 03 (DB pull), doc 13 (formulas), doc 07 (UX) | **L** |
| **P2 — Live supervisor wallboard** | Realtime | Call Control API connector; live calls-waiting / longest-wait / agent-state tiles over Channels; Monitor/Whisper/Barge; threshold alerts + escalation (fix recipient routing, real worker) | doc 08 (alerts), Call Control API | **L** |
| **P3 — Agent-state layer** | Occupancy/adherence | `AgentState`/`Disposition` event stream; Occupancy, true ACW/wrap, Aux/Not-Ready codes, shrinkage; (WFM `Schedule` for Adherence/Utilization) | P2 feed | **XL** |
| **P4 — Quality & experience** | QA + survey | `Recording` ingest + transcript/sentiment; `Scorecard`/`Evaluation`/`Calibration`; post-call CSAT/NPS survey subsystem; operational FCR (caveated) + true FCR via CRM | recordings, survey channel | **XL** |
| **P5 — Voice quality** | QoS/MOS | RTCP-XR / 3CX Call Quality ingestion to populate `mos`/`jitter_ms`/`packet_loss_pct`/`latency_ms`; MOS dashboards (device-reported or E-model) | QoS feed | **L** |

P0 is days of work and directly closes the open `issues.txt` complaint. P1 makes the product credible. P2-P5 are the differentiators 3CX itself does not provide, and each is vendor-neutral by construction.

---

### Cross-references

- Schema DDL, indexing, partitioning, query performance → [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md)
- Ingestion transports (socket vs DB pull vs Call Control API), casing normalization at ingest → [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md)
- Precise KPI formulas, denominators, benchmarks, E-model MOS → [13-Call-Center-KPI-and-Metrics-Reference.md](13-Call-Center-KPI-and-Metrics-Reference.md)
- Wallboard/dashboard UX, widgets, charts, exports, scheduled reports → [07-Reporting-Dashboards-and-UI-UX.md](07-Reporting-Dashboards-and-UI-UX.md)
- Alert-rules engine, escalation, email/SMS/WhatsApp, runtime (no Celery today) → [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md)
- Vendor-neutral CDR, adapter pattern, Cisco CUCM/Teams/Webex/Zoom, intelligence layer → [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md)
- Consolidated gap matrix & backlog → [11-Gap-Analysis-and-Feature-Backlog.md](11-Gap-Analysis-and-Feature-Backlog.md); phased roadmap → [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md)
