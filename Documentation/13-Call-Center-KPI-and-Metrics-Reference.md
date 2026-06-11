# Call Center KPI & Metrics Reference

> **Purpose.** This is the canonical reference appendix for the connect.zentryc.com platform: a single source of truth for every contact-center KPI we report on, with a precise definition, formula, the exact CDR columns it maps to, a worked example against our live data, and a note on what extra data (if any) is required. It exists so that the dashboards, reports, alert thresholds, and the call-center evaluation module described in [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md) all compute the *same* number the *same* way. Where a metric cannot be computed from today's 3CX socket CDR, this document says so explicitly and points to the data source that would unlock it.

## TL;DR / Key Takeaways

- **Answered/unanswered is already derivable** — and the app gets it wrong. `time_answered IS NULL` cleanly identifies the **461,602 of 1,492,192 calls (30.9%)** that were never answered (verified 2026-06-05). The current code instead matches `reason_terminated='NoAnswer'`, a literal **that does not exist in the data** — that filter matches **zero rows** and is the direct cause of the open "call Statics not showing data" complaint (`/home/ubuntu/3CX/issues.txt`).
- **Two data-quality bugs poison almost every filter.** The `*_type` fields *and* `reason_terminated` both contain mixed-case duplicates (`Ivr`/`ivr`, `Extension`/`extension`, `src_participant_terminated`/`TerminatedBySrc`). The call-center module uses exact-case filters (`Q(to_type='Ivr')`, `final_type='Extension'`) at `cdr3cx/callcenter_views.py:52,68,104` and so **silently drops roughly half** of relevant records. Every formula below is specified **case-insensitively (`LOWER()`)**.
- **Computable from the CDR today (after the two fixes + a `call_time` index):** Service Level, ASA, Abandonment (+ short-abandon), Average Wait, Answer/Miss rate, and *talk-time-based* handle time. Worked: ASA over the answered set is **10.7 s** across **1,030,590** answered calls; Service Level 80/20 over IVR-routed calls is **249,104 / 250,101 ≈ 99.6%** (sample run 2026-06-05).
- **NOT computable from the CDR — needs a new data source:** AHT (true), Hold, ACW/Wrap, Occupancy, Utilization, Schedule Adherence, true queue-Abandon vs no-answer, FCR, Longest/oldest wait (real-time), Agent-state durations, CSAT/NPS/CES, and **MOS** (the `mos`/`jitter_ms`/`packet_loss_pct`/`latency_ms` columns are **100% NULL — 0 of 1.49M rows**). These require the agent/queue model layer, a QoS feed, surveys, or the 3CX Call Control API. See [05](05-Call-Center-Evaluation-Module.md) and [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md).
- **No `call_time` index exists** (confirmed: indexes cover only `company_id`, `source_pbx`, `external_id`, `correlation_id`). Every metric here filters a `call_time` range over 1.49M rows. Add `(company_id, call_time)` before scaling — see [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md).

---

## 1. How to read this reference

Each metric entry below follows a fixed shape:

- **Definition** — the industry-standard plain-English meaning.
- **Formula** — the arithmetic, with the denominator variant stated explicitly (this matters most for Service Level and Abandonment).
- **Source fields** — the exact `cdr3cx_callrecord` columns used (see [04](04-Data-Model-and-Database-Performance.md) for the schema), or the new data source required.
- **Worked example** — a concrete calculation, grounded in our live numbers where possible.
- **Extra data required** — what we must add before the metric is real.
- **Feasibility tag** — **Today** (computable now after the data-quality + index fixes), **Phase-2** (needs the new agent/queue/state model), or **New-source** (needs QoS, surveys, CRM, or Call Control API).

### 1.1 Derived quantities used throughout

All time-based KPIs derive from three primitives on the existing schema (`cdr3cx/models.py:119–125`):

| Derived quantity | Expression | Notes |
|---|---|---|
| `wait` (queue/ring time) | `time_answered − call_time` (answered) **or** `time_end − call_time` (unanswered) | seconds; clamp negatives to 0 |
| `talk` (handle time, talk only) | `time_end − time_answered`, or the existing `duration` integer (seconds) | `duration` is `integer` seconds (verified) — **not** full AHT |
| `answered` | `time_answered IS NOT NULL` | the single most reliable signal; 1,030,590 rows |
| `unanswered` | `time_answered IS NULL` | 461,602 rows (30.9%) |

> **Caveat on `wait` for unanswered calls.** `time_end − call_time` for an unanswered row is the *time-before-disposition*, not necessarily "time the caller chose to wait" — it also covers system failures (`Failed`, `no_route`, `busy`, `declined`). Those must be classified separately (see §2) before they are counted as customer wait/abandon.

---

## 2. Canonical answered / missed / abandoned / system-disposed classification (adopt this first)

This is the **foundational logic** the platform must standardize on; every rate metric depends on it. The current heuristics (`final_type='Extension'` = answered; `reason_terminated='NoAnswer'` = missed) are both broken — the first is case-sensitive and drops ~half the data, the second matches no rows at all.

**Live `reason_terminated` distribution (verified 2026-06-05):** `src_participant_terminated` (494,775), `TerminatedBySrc` (301,009), `dst_participant_terminated` (216,793), `TerminatedByDst` (161,553), `Failed` (161,079), `no_route` (54,032), `declined` (37,442), `not_found` (24,377), `timeout` (5,458), `busy` (1,258). Note the **mixed-case duplicates** (`src_participant_terminated` vs `TerminatedBySrc`) — the same disease as the `*_type` fields — and the **absence of any `NoAnswer` literal**.

### 2.1 Canonical disposition classes

| Class | Rule (case-insensitive) | Meaning |
|---|---|---|
| **Answered** | `time_answered IS NOT NULL` | An agent/endpoint connected. |
| **Abandoned** | `time_answered IS NULL` AND it was an inbound, customer-facing queue/IVR call AND `reason_terminated` indicates the *caller* released (`src_participant_terminated` / `terminatedbysrc` / caller hang-up) | Customer hung up while waiting. The metric that matters. |
| **Short-abandon** | Abandoned AND `(time_end − call_time) ≤ short_abandon_threshold` (default 5–10 s, configurable) | Misdials; excluded from the headline abandon rate. |
| **System-disposed** | `time_answered IS NULL` AND `reason_terminated IN (failed, no_route, not_found, busy, declined, timeout)` | Network/routing/busy failures — **not** customer abandonment. Report separately. |

### 2.2 Reference ORM snippet (case-insensitive, adopt verbatim)

```python
from django.db.models import Q, F, Count, Avg, Sum, Case, When, Value, BooleanField
from django.db.models.functions import Lower, Extract

# --- canonical building blocks -------------------------------------------------
ANSWERED      = Q(time_answered__isnull=False)
UNANSWERED    = Q(time_answered__isnull=True)

CALLER_RELEASED = Q(reason_terminated__iexact='src_participant_terminated') | \
                  Q(reason_terminated__iexact='TerminatedBySrc')

SYSTEM_FAIL = Q(reason_terminated__iregex=r'^(failed|no_route|not_found|busy|declined|timeout)$')

# "Call-center / queue" call identification — CASE-INSENSITIVE (fixes the flagship bug)
IS_CC = (Q(to_type__iexact='ivr') | Q(final_type__iexact='ivr')
         | Q(to_dispname__icontains='call center'))

ABANDONED = UNANSWERED & CALLER_RELEASED & ~SYSTEM_FAIL

qs = CallRecord.objects.filter(company=company, call_time__range=(start, end)).filter(IS_CC)

stats = qs.aggregate(
    offered       = Count('id'),
    answered      = Count('id', filter=ANSWERED),
    abandoned     = Count('id', filter=ABANDONED),
    system_failed = Count('id', filter=UNANSWERED & SYSTEM_FAIL),
)
```

> **Note on `__iexact` / `__iregex`.** These work today but apply `LOWER()` at query time, which cannot use a plain index. The durable fix is to **normalize casing at ingest** into canonical lowercase enums (and add a generated `call_disposition` column), so filters become equality on an indexable value. See the ingestion redesign in [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md) and the schema change in [04](04-Data-Model-and-Database-Performance.md).

---

## 3. Time-based KPIs — computable from the CDR today

### 3.1 Service Level (SL) — *the #1 missing KPI*

- **Definition.** Percentage of calls answered within a configured target time, written `X/Y` (e.g. **80/20** = 80% answered within 20 seconds).
- **Formula (state the denominator).**
  `SL% = (answered within target ÷ denominator) × 100`, where the denominator is one of:
  - `answered + abandoned` (excludes short-abandon) — **recommended default**, or
  - `total offered` (counts every inbound call), or
  - `answered only` (most generous).
  The chosen variant must be displayed next to the number.
- **Source fields.** `time_answered`, `call_time`; abandon classification per §2; `short_abandon_threshold` and `sla_target_seconds` from a new **ThresholdPolicy** (per tenant/queue — does not exist yet).
- **Worked example (live, sample 2026-06-05).** Over IVR-routed calls, **249,104** were answered within 20 s out of **250,101** offered → **SL 80/20 = 99.6%** (denominator = total offered). This is unusually high because most IVR-routed legs are answered by the IVR app near-instantly; *real* SL must be scoped to actual agent queues (Phase-2, via the queue model), not all IVR legs — a caveat the current heuristic cannot express.
- **Extra data required.** Configurable per-queue `sla_target_seconds`; a real queue boundary (Phase-2). **Today** for an approximate tenant-wide SL; **Phase-2** for per-queue SL.
- **Tag:** Today (approx) → Phase-2 (per-queue).

```sql
-- Service Level 80/20, denominator = answered + abandoned, case-insensitive CC scope
SELECT 100.0 * count(*) FILTER (
         WHERE time_answered IS NOT NULL
           AND EXTRACT(EPOCH FROM (time_answered - call_time)) <= 20)
       / NULLIF(count(*) FILTER (WHERE time_answered IS NOT NULL
                                    OR reason_terminated ILIKE 'src_participant_terminated'
                                    OR reason_terminated ILIKE 'TerminatedBySrc'), 0) AS sl_80_20
FROM cdr3cx_callrecord
WHERE company_id = %s AND call_time >= %s AND call_time < %s
  AND (lower(to_type) = 'ivr' OR lower(final_type) = 'ivr');
```

### 3.2 Average Speed of Answer (ASA)

- **Definition.** Average queue/ring wait experienced by **answered** calls before connection. Weaker than SL (an average hides the distribution) — always show **alongside** SL, never instead of it.
- **Formula.** `ASA = Σ(time_answered − call_time) over answered ÷ count(answered)`.
- **Source fields.** `time_answered`, `call_time`. No new data needed.
- **Worked example (live, verified).** `AVG(time_answered − call_time)` over the **1,030,590** answered rows = **10.7 seconds**. (Benchmark: industry ~28 s; Calabrio target ≈ 25% of AHT.)
- **Extra data required.** None — only the missing `call_time` index to avoid a sequential scan of 1.49M rows.
- **Tag:** Today.

### 3.3 Average Wait Time (queue)

- **Definition.** Average time *all* callers waited, whether they were answered or abandoned (broader than ASA, which is answered-only).
- **Formula.** `AvgWait = Σ wait ÷ (answered + abandoned)`, where `wait = time_answered − call_time` (answered) or `time_end − call_time` (abandoned, excluding system-disposed).
- **Source fields.** `time_answered`, `time_end`, `call_time`, disposition per §2.
- **Worked example.** Suppose 100 answered (total wait 1,000 s) and 20 abandoned (total wait 600 s): `AvgWait = 1,600 ÷ 120 = 13.3 s`.
- **Tag:** Today.

### 3.4 Longest / Oldest Wait

- **Definition.** *Historical:* the maximum wait observed in a period. *Real-time:* the duration the **oldest currently-waiting** caller has been in queue — the single best supervisor-intervention trigger.
- **Formula.** Historical: `MAX(wait)`. Real-time: `now() − oldest_queued_call.entered_at` (live).
- **Source fields.** Historical: `wait` per §1.1. **Real-time: NOT in the CDR** — the CDR is written only at call end and has no live queue state.
- **Extra data required.** Real-time longest-wait needs a **live queue feed** (3CX Call Control / Queue API) pushed to the Channels/Redis wallboard — see [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md).
- **Tag:** Today (historical) → New-source (real-time).

### 3.5 Abandonment Rate (+ Short-Abandon)

- **Definition.** Percentage of inbound calls where the caller hung up before being answered. Short calls (≤ threshold) are excluded as misdials.
- **Formula.**
  `Abandon% = (abandoned − short_abandon) ÷ (offered − short_abandon) × 100`.
  Benchmarks: good ≈ 2%, acceptable ≈ 5%.
- **Source fields.** Disposition per §2 (`time_answered IS NULL` + caller-released + not system-disposed); `short_abandon_threshold` (new ThresholdPolicy); `time_end − call_time` for the short-abandon test.
- **Worked example.** 1,000 offered; 120 unanswered, of which 30 are system-disposed (`Failed`/`no_route`) and 15 are short-abandons (≤ 5 s). True abandons = 120 − 30 − 15 = 75. `Abandon% = 75 ÷ (1,000 − 15) = 7.6%`.
- **Extra data required.** Configurable `short_abandon_threshold`; correct system-disposed exclusion. **Caution:** lumping `Failed`/`no_route`/`busy`/`declined` into abandonment (as a naive `time_answered IS NULL` count would) overstates it materially given **161,079 `Failed` + 54,032 `no_route`** rows in the data.
- **Tag:** Today.

### 3.6 Answer Rate & Miss Rate

- **Definition.** Share of offered calls that were answered (Answer Rate) vs not (Miss Rate).
- **Formula.** `AnswerRate% = answered ÷ offered × 100`; `MissRate% = 100 − AnswerRate%`.
- **Source fields.** `time_answered` (answered = NOT NULL), case-insensitive CC scope per §2.2.
- **Worked example (live, all calls).** `1,030,590 ÷ 1,492,192 = 69.1%` answer rate; **30.9% miss rate**. *Replaces* the broken `reason_terminated='NoAnswer'` logic at `callcenter_views.py:57,105,158` (which returns 0 missed) and the case-sensitive `final_type='Extension'` answered count at `:68,104`.
- **Tag:** Today. **This single fix resolves the open issue in `/home/ubuntu/3CX/issues.txt`.**

### 3.7 Callback Success Rate

- **Definition.** Of abandoned/missed calls a supervisor or agent attempted to call back, the fraction subsequently answered.
- **Formula.** `CallbackSuccess% = callbacks answered ÷ callbacks attempted × 100`.
- **Source fields.** The current `call_back_tracking` view (`callcenter_views.py:401–502`) infers this by re-querying the same caller number — but it runs **nested per-number queries inside a Python loop (N+1)** and uses the broken miss filter. Rebuild as a single set-based query keyed on `from_no` with a windowed self-join.
- **Extra data required.** A first-class outbound/callback marker. A *true* queue-callback (virtual hold) is a **call-control** feature (Call Control API), not analytics — see [05](05-Call-Center-Evaluation-Module.md).
- **Tag:** Today (approx) → New-source (true virtual-hold callback).

---

## 4. Handle-time KPIs — partially computable

### 4.1 Talk Time

- **Definition.** Time the agent and caller were actually connected.
- **Formula.** `Talk = time_end − time_answered`, or the existing `duration` integer (seconds).
- **Source fields.** `time_end`, `time_answered`, or `duration`.
- **Worked example.** `time_answered=10:00:09`, `time_end=10:04:19` → talk = 250 s; matches the `duration` int for that row.
- **Tag:** Today. **Label this "Talk/Handle time", never "AHT"** — see §4.4.

### 4.2 Hold Time

- **Definition.** Time the caller spent on hold during a connected call.
- **Source fields.** **Not in the CDR.** A single-leg 3CX socket record has no hold events.
- **Extra data required.** Per-leg events from the 3CX Call Control API or v20 `cdr_output` granular timestamps; a `hold_time` column (proposed in [04](04-Data-Model-and-Database-Performance.md)).
- **Tag:** New-source.

### 4.3 After-Call Work (ACW) / Wrap Time

- **Definition.** Post-call period where the agent finalizes the interaction (notes, CRM, disposition) and is unavailable for new ACD calls — a distinct **Wrap-Up** agent state.
- **Source fields.** **Not in the CDR and not inferable.** 3CX itself does not natively track agent-controlled wrap (agents "log out to do paperwork").
- **Extra data required.** An `AgentState` event stream (Wrap-Up state with start/stop) and a `Disposition`/`WrapCode` model — the agent-state layer in [05](05-Call-Center-Evaluation-Module.md).
- **Tag:** Phase-2.

### 4.4 Average Handle Time (AHT) — *true*

- **Definition.** `AHT = (Talk + Hold + ACW) ÷ calls handled` (Genesys adds outbound dialing/contacting time). Industry avg ≈ 6m10s; talk ≈ 60–70%, ACW ≈ 15–30%.
- **Source fields.** Only **Talk** is available today. Hold and ACW are missing (§4.2, §4.3).
- **Extra data required.** Hold + ACW data. Until then, present **"Talk/Handle time"** and clearly mark AHT as Phase-2; calling `duration` "AHT" would overstate productivity by understating effort.
- **Tag:** Phase-2.

---

## 5. Agent-efficiency KPIs — require the agent-state layer

None of these can be mined from the CDR; all require agent login/logout, available-vs-idle, and (for Utilization/Adherence) schedule data. They are the primary justification for the vendor-neutral `Queue` / `Agent` / `AgentState` / `Disposition` model layer in [05](05-Call-Center-Evaluation-Module.md) and [10](10-Multi-Vendor-and-Target-Architecture.md).

### 5.1 Occupancy

- **Definition.** Of logged-in-and-available time, the share spent on call-related work. Target ≈ 70–90%.
- **Formula.** `Occupancy = (Talk + Hold + ACW) ÷ (Talk + Hold + ACW + Idle/Available) × 100`.
- **Source fields.** Requires `AgentState` durations (Available vs On-Call vs Wrap). **Not in the CDR.**
- **Tag:** Phase-2.

### 5.2 Utilization

- **Definition.** Productive handling time ÷ **total paid/logged-in shift time** (includes shrinkage: breaks, training, meetings). Target ≈ 75–85%.
- **Formula.** `Utilization = (Handle + ACW) ÷ Total Logged-In Time × 100`.
- **Source fields.** `AgentState` login/logout durations + shift data. **Not in the CDR.**
- **Tag:** Phase-2 (Utilization also needs WFM shift data).

> **Occupancy vs Utilization** — the denominator differs: Occupancy = *available* time; Utilization = *total shift* time. Keep them distinct in the UI.

### 5.3 Schedule Adherence

- **Definition.** Share of scheduled time the agent was present in the correct state. `Adherence = Minutes in Adherence ÷ Total Scheduled Minutes × 100`. (Conformance = total worked vs scheduled, ignoring timing.)
- **Source fields.** A **WFM Schedule** model (planned shifts) **and** `AgentState` timestamps to compare against. Neither exists.
- **Extra data required.** Schedule model + agent-state events — a Phase-2/WFM capability dependent on the agent-state layer.
- **Tag:** Phase-2.

### 5.4 Agent State Durations (Aux / Not-Ready codes)

- **Definition.** Time per agent in each ACD state: Offline, Available/Ready, Reserved, On-Call/Talking, Wrap-Up, Not-Ready/Aux (with reason codes: Break, Lunch, Training, Meeting, Coaching).
- **Formula.** `Σ(state_end − state_start)` grouped by `(agent, state, reason_code)`.
- **Source fields.** New `AgentState(agent, state, reason_code, started_at, ended_at)` model populated from a presence feed (3CX Call Control API WebSocket, or agent-desktop events). Designed vendor-neutrally so Cisco Finesse states map onto the same model — see [10](10-Multi-Vendor-and-Target-Architecture.md).
- **Tag:** Phase-2.

---

## 6. Quality & experience KPIs — net-new data sources

### 6.1 First Contact Resolution (FCR)

- **Definition.** Share of contacts resolved on the first interaction. `FCR = resolved-first-contact ÷ total contacts × 100`. Industry 70–75%; world-class ≥ 80%.
- **Source fields.** Not in a single-leg CDR. An **operational approximation** is possible: detect repeat contacts from the same `from_no` to the same queue within a rolling window (e.g. 24–72 h) and treat non-repeats as resolved.
- **Extra data required.** True FCR needs CRM case linkage and/or a post-call survey (SQM-style self-report). **Caveat the approximation:** caller-ID matching is imperfect and `from_no` can be **truncated by the 1024-byte socket `recv()`** (`socket_server.py`) — see [03](03-CDR-Ingestion-and-3CX-Integration.md).
- **Tag:** New-source (approx Today with caveats).

### 6.2 CSAT / NPS / CES

| Metric | Formula | Scope |
|---|---|---|
| **CSAT** | `top-box positive responses ÷ total responses × 100` | per interaction (transactional) |
| **CES** | average of 1–7 "made it easy" responses | per interaction (effort) |
| **NPS** | `%Promoters(9–10) − %Detractors(0–6)` | relationship-level (periodic) |

- **Source fields.** None — require a **post-call survey subsystem** (IVR/SMS/email/web survey, response capture model), mapped back to the `CallRecord`/agent. Ties into the "rich alerts/emails" requirement (survey invites) — see [08](08-Realtime-Alerts-and-Notifications.md).
- **Tag:** New-source.

### 6.3 MOS / Voice Quality (Jitter, Packet Loss, Latency)

- **Definition.** Mean Opinion Score rates voice quality 1 (bad) to 5 (excellent); business target ≈ 4.0–4.4.
- **Formula (ITU-T G.107 E-model).**
  `R = 93.2 − Id − Ie + A` (Id = delay impairment, Ie = codec + packet-loss impairment, A = advantage factor); then
  `MOS = 1 + 0.035·R + 7×10⁻⁶·R·(R − 60)·(100 − R)`.
  Drivers: latency noticeable > 150 ms / breaks down > 300 ms; ~1% packet loss ≈ −0.4 MOS.
- **Source fields.** The schema **has** `mos`, `jitter_ms`, `packet_loss_pct`, `latency_ms`, `codec` (`models.py:110–114`) — **but they are 100% NULL (0 of 1,492,192 rows, verified).** The 3CX socket CDR carries **no QoS**.
- **Extra data required.** A QoS feed: 3CX Call Quality / RTCP-XR / SIP PUBLISH, an SBC/probe, or (multi-vendor) Cisco CMR / Teams media segments / Webex media — then store device-reported MOS or compute from the R-factor above. A "call quality" dashboard is **empty until this feed exists** — a separate ingestion workstream in [10](10-Multi-Vendor-and-Target-Architecture.md).
- **Tag:** New-source.

---

## 7. Direction inference (prerequisite for inbound-only metrics)

Abandonment, SL, and ASA must be scoped to **inbound** calls. Direction is **not a stored column** but is inferable from the normalized `*_type` fields:

| Pattern (case-insensitive) | Direction |
|---|---|
| `from_type` ∈ {`line`, `provider`} (external trunk on the from-side) | **Inbound** |
| `from_type` = `extension` AND `to_type`/`final_type` ∈ {`line`, `provider`} | **Outbound** |
| `from_type` = `extension` AND `to_type` = `extension` | **Internal** |

Live `from_type` distribution (verified): `extension` 697,777 + `Extension` 539,738, `provider` 138,333, `Line` 115,716, `Ivr` 450 + `ivr` 143 — again confirming the mixed-casing that **must be normalized (`LOWER()`) first**. Recommendation: add a persisted, normalized `direction` column at ingest (proposed in [04](04-Data-Model-and-Database-Performance.md)) rather than re-deriving it in every query.

---

## 8. Master KPI feasibility matrix

| KPI | Formula (short) | Source fields / new source | Feasibility | Severity if missing | Effort |
|---|---|---|---|---|---|
| Service Level | answered≤T ÷ (ans+aband) | `time_answered`,`call_time`,ThresholdPolicy | Today→Phase-2 | Critical | M |
| ASA | Σ wait(ans) ÷ ans | `time_answered`,`call_time` | Today | High | S |
| Average Wait | Σ wait ÷ (ans+aband) | `time_answered`,`time_end`,`call_time` | Today | High | S |
| Longest/Oldest Wait | MAX(wait) / live | CDR / **live queue feed** | Today→New-source | High | M |
| Abandonment (+short) | (aband−short) ÷ (offered−short) | §2 disposition, ThresholdPolicy | Today | Critical | M |
| Answer/Miss Rate | answered ÷ offered | `time_answered` | Today | Critical | S |
| Callback Success | answered ÷ attempted | `from_no`,`time_answered` | Today→New-source | Medium | M |
| Talk Time | `time_end − time_answered` | `time_end`,`time_answered`,`duration` | Today | Low | S |
| Hold Time | per-leg hold events | **Call Control API** | New-source | Medium | L |
| ACW / Wrap | wrap state duration | **AgentState** | Phase-2 | High | L |
| AHT (true) | (talk+hold+ACW) ÷ handled | talk + **Hold + ACW** | Phase-2 | High | L |
| Occupancy | work ÷ available | **AgentState** | Phase-2 | High | L |
| Utilization | (handle+ACW) ÷ logged-in | **AgentState + WFM** | Phase-2 | Medium | L |
| Schedule Adherence | adherent ÷ scheduled | **Schedule + AgentState** | Phase-2 | Medium | XL |
| Agent State Durations | Σ state durations | **AgentState** | Phase-2 | High | L |
| FCR | resolved-first ÷ total | repeat-contact / **CRM+survey** | New-source | Medium | L |
| CSAT / NPS / CES | see §6.2 | **Survey subsystem** | New-source | Medium | L |
| MOS / QoS | E-model R-factor | **QoS feed** (cols 100% NULL) | New-source | Medium | L |

---

## 9. Computation & accuracy guardrails

1. **Normalize at ingest, not in queries.** Canonicalize `*_type` and `reason_terminated` to lowercase enums in the ingestion adapter ([03](03-CDR-Ingestion-and-3CX-Integration.md)), and add a generated `call_disposition` + `direction` column ([04](04-Data-Model-and-Database-Performance.md)). Then KPI queries become indexable equality checks instead of `LOWER()`/`ILIKE` scans.
2. **One ThresholdPolicy, three consumers.** A single per-tenant/per-queue policy (`sla_target_seconds`, `short_abandon_seconds`, alert thresholds) must drive (a) the SL/abandon **formulas**, (b) wallboard **color** (green/amber/red), and (c) **alert/escalation** firing — see [05](05-Call-Center-Evaluation-Module.md) and [08](08-Realtime-Alerts-and-Notifications.md). Pair every dashboard number with its target.
3. **Index before you aggregate.** Add `(company_id, call_time)`; replace the dashboard's 24 per-hour + 21 daily individual `COUNT` scans and the `call_back_tracking` N+1 loop with single `GROUP BY date_trunc(...)` queries or a materialized rollup ([04](04-Data-Model-and-Database-Performance.md), [07-Reporting-Dashboards-and-UI-UX.md](07-Reporting-Dashboards-and-UI-UX.md)).
4. **Two paths, never confused.** Historical KPIs (SL, ASA, abandonment, trends) come from the **CDR** (indexed, aggregated). Real-time KPIs (oldest wait, agents available, live SL) come from a **live queue feed** over Channels/Redis — never from the CDR table, which writes only at call end ([08](08-Realtime-Alerts-and-Notifications.md)).
5. **State the denominator and the timezone.** Always render SL as `X/Y` with its denominator variant, and compute period boundaries in `Asia/Riyadh` (`TIME_ZONE`, see [09-Security-and-Compliance.md](09-Security-and-Compliance.md)); the multi-call-center future (3CX San Francisco) will require per-tenant timezones — see [10](10-Multi-Vendor-and-Target-Architecture.md).

---

## 10. Where these metrics are consumed

- **Call-center evaluation, agent/queue/state model, supervisor & QA scorecards:** [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md) (the primary consumer of this reference).
- **Dashboards, report catalog, charting, exports:** [07-Reporting-Dashboards-and-UI-UX.md](07-Reporting-Dashboards-and-UI-UX.md).
- **Real-time wallboard, thresholds, alerts/escalations:** [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md).
- **Schema changes, indexing, partitioning, missing entities:** [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md).
- **Casing normalization, ingestion redesign, v20 `cdr_output`/queue views:** [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md).
- **Vendor-neutral CDR, QoS/MOS feeds, Call Control API, Cisco/Teams/Webex/Zoom mapping:** [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md).
- **Prioritized backlog and phased delivery for these KPIs:** [11-Gap-Analysis-and-Feature-Backlog.md](11-Gap-Analysis-and-Feature-Backlog.md), [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md).

> *This document supersedes the KPI/metric content in the older `/home/ubuntu/3CX/enhancement/*.md` business-strategy set for engineering purposes; those remain the reference for market/pricing strategy only.*
