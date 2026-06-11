# Reporting, Dashboards & UI/UX

This document audits the current reporting surface, dashboards, and UI stack of the `connect.zentryc.com` 3CX portal, benchmarks it against mature UC/contact-center analytics products (Variphy, Xima Chronicall, Tollring, Brightmetrics, Imagicle, Nectar), and specifies a target reporting architecture, a `connect.zentryc.com` design system (dark/light, responsive, accessible, Arabic/RTL), and concrete dashboard redesigns with wireframes. It is the presentation-layer counterpart to the data-model work in [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md), the metric science in [13-Call-Center-KPI-and-Metrics-Reference.md](13-Call-Center-KPI-and-Metrics-Reference.md), the call-center module in [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md), and the realtime/alerting plumbing in [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md).

## TL;DR / Key Takeaways

- **The reporting layer is functionally rich on paper but architecturally fragile.** There are ~20 report/dashboard views and working CSV/Excel/PDF exports (`cdr3cx/views_reports.py`, `import_export`, `openpyxl`, `reportlab`), but every dashboard filters `call_time` over **1,492,192 rows with no index on `call_time`** (verified: indexes exist only on `company_id`, `source_pbx`, `external_id`, `correlation_id`) — sequential scans on every page load.
- **"Scheduled reports" do not exist and could not run anyway.** There is **no `ScheduledReport` model anywhere** in the codebase, and production has **no Celery/cron worker** running (systemd hosts only gunicorn/daphne/socket_server). Any "scheduled" or "async" reporting is vaporware until a worker exists — see [08](08-Realtime-Alerts-and-Notifications.md) and [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md).
- **The call-center dashboard silently drops ~half its data and queries it ~50× per page.** `cdr3cx/callcenter_views.py:52` filters `Q(to_type='Ivr')` case-sensitively — production has `Ivr` (112,642) **and** `ivr` (136,928); and the "missed" predicate `reason_terminated='NoAnswer'` (lines 57/105/158/363) **matches 0 of 1.49M rows** (verified). This is the open "call Statics not showing data" complaint.
- **The UI foundation is better than it's being used.** The portal is built on the **Velzon Bootstrap 5 admin theme**, which already ships `app-rtl.min.css` and `bootstrap-rtl.min.css` and a theme `data-theme`/customizer mechanism in `/static/css` — dark mode and Arabic/RTL are **packaged but unwired**. Charting is a single CDN `chart.js` include with hand-rolled `<canvas>` blocks.
- **Target:** an indexed, pre-aggregated reporting service; a report-builder + a real scheduled-report engine (running on the new worker); widget-based drag-drop role dashboards (exec / call-control / billing / call-center) with dark mode and RTL turned on; cradle-to-grave drill-down keyed on `correlation_id`; and exports unified into one renderer (CSV/XLSX/PDF).

---

## 1. Current Reporting & Dashboard Inventory

The reporting surface is spread across `cdr3cx/views.py` (48 KB), `cdr3cx/views_reports.py`, `cdr3cx/callcenter_views.py`, `cdr3cx/quota_views.py`, and the `realtime` app, routed in `cdr3cx/urls.py`.

| Area | Views / routes (file:line) | Template | Export | Notes |
|---|---|---|---|---|
| Executive dashboard | `views.py:221 dashboard()` (`/dashboard/`) | `cdr/dashboard.html` | — | Cost + volume tiles; pulls **every row into Python** for country counting (`views.py` `for record in call_records` → `Counter`) |
| All calls / search | `views.py` `all_calls_view` (`/all_calls/`) | `cdr/all_calls1.html` | — | `Paginator` (server-side page slicing only; still scans) |
| Incoming / Outgoing / Internal | `/incoming/`, `/outgoing/`, `/outgoing_international/` | `incomingCalls.html` etc. | XLSX/PDF | Per-direction filtered lists |
| International by country | `/international-calls/<slug>/` | `country_specific_calls.html` | XLSX/PDF (`views_reports.py:17,53`) | `openpyxl` + `reportlab` |
| Caller drill-down | `/caller-calls/<num>/` | `caller_calls.html` | XLSX/PDF (`views.py:837,872`) | Per-caller history |
| Top extensions | `/top-extensions/` (+`/excel-report/`, `/pdf/`) | `top_extensions.html` | XLSX/PDF | Leaderboards |
| Sales / summary reports | `/sales-reports/`, `/summary/` | `sales_reports.html`, `call_record_summary.html` | — | Aggregate rollups |
| Quota | `quota_views.py` (`/quotas/...`) | `cdr/quota/*` | Email | `quota_status_email.html` |
| Call-center dashboard | `callcenter_views.py:13` (`/call-center/`) | `cdr/callcenter/dashboard.html` | — | Chart.js daily-trends + hourly |
| Agent / missed / callback | `/call-center/agent/...`, `/missed-calls/`, `/call-back-tracking/` | `callcenter/*.html` | — | N+1 in `call_back_tracking` |
| Realtime wallboard | `realtime/` (Channels, `/ws`) | `realtime/wallboard.html` | — | Snapshot via `realtime/snapshot.py` |

**UI stack (verified in `cdr/settings.py` and `/static`):**

| Layer | What is present | Maturity |
|---|---|---|
| CSS framework | **Velzon** admin theme on **Bootstrap 5** (`templates/partials/base.html:6` title "Velzon - Admin & Dashboard Template") | Modern theme, lightly used |
| Forms | `crispy_forms` + `crispy_bootstrap4` (`CRISPY_TEMPLATE_PACK = 'bootstrap4'`) | **Version mismatch:** crispy pinned to BS4 while layout is BS5 |
| Tables/exports | `import_export`, `openpyxl`, `reportlab` | Working but bespoke per-view |
| Charting | `chart.js` via CDN (`callcenter/dashboard.html:416`), hand-coded `<canvas>` | Ad-hoc, no shared chart helper |
| Icons | Font Awesome 6.5 (CDN) + Velzon icon fonts | OK |
| i18n / RTL | `USE_I18N = True`, `LANGUAGE_CODE = 'en-us'`, **no `LocaleMiddleware`, no `gettext` usage, `app-rtl.min.css` shipped but never linked** | **Not wired** |
| Realtime | Channels + Redis + daphne (`/ws`) | Plumbed, thin |

> **Finding (High):** crispy is configured for `bootstrap4` (`settings.py:148`) while the page chrome is Velzon/Bootstrap 5. Forms render against a different grid/utility set than the surrounding layout — a quiet source of visual inconsistency. **Recommendation:** install `crispy-bootstrap5` and set `CRISPY_TEMPLATE_PACK = 'bootstrap5'`.

---

## 2. Critical Reporting Defects (evidence-led)

These are presentation-layer bugs; the data model behind them is covered in [04](04-Data-Model-and-Database-Performance.md) and the metric definitions in [13](13-Call-Center-KPI-and-Metrics-Reference.md).

| # | Defect | Evidence (path:line / DB) | Severity | Effort |
|---|---|---|---|---|
| R1 | No `call_time` index → every report seq-scans 1.49M rows | `pg_indexes`: only `company_id`/`source_pbx`/`external_id`/`correlation_id` | Critical | S |
| R2 | Case-sensitive `to_type='Ivr'` drops ~half of call-center data | `callcenter_views.py:52`; DB `Ivr`=112,642 vs `ivr`=136,928 | Critical | S |
| R3 | "Missed" predicate `reason_terminated='NoAnswer'` matches **0 rows** | `callcenter_views.py:57,105,158,363`; also `realtime/snapshot.py:30-31`; `SELECT count(*) … ='NoAnswer'` → **0** | Critical | S |
| R4 | Call-center dashboard runs **24 per-hour COUNT + 7×3 daily COUNT** scans | `callcenter_views.py:137-144`, `148-170` | High | M |
| R5 | `call_back_tracking` N+1: per-number loop, ~5 queries/iteration ×100 | `callcenter_views.py:394-449` | High | M |
| R6 | Exec dashboard materializes **all rows into Python** for country counts | `views.py` `for record in call_records` → `Counter(countries)` | High | M |
| R7 | No `ScheduledReport` model; no worker to run one | codebase grep (none); systemd = gunicorn/daphne/socket only | High | L |
| R8 | Exports are per-view bespoke (`openpyxl`/`reportlab` copied per report) | `views_reports.py:17,53,173`; `views.py:837,866` | Medium | M |
| R9 | RTL/i18n shipped but unwired; no `LocaleMiddleware` | `app-rtl.min.css` present, never linked; no `gettext` | Medium | M |
| R10 | Dark mode (Velzon `data-theme`) not exposed to users | `partials/base.html:3` `data-theme="default"` only | Low | S |

**R1 fix (one migration, immediate win):**

```python
class Meta:
    indexes = [
        models.Index(fields=["company", "call_time"], name="cdr_company_calltime_idx"),
        models.Index(fields=["company", "call_time", "to_type"], name="cdr_cc_filter_idx"),
    ]
```

**R2/R3 fix (normalize at the query boundary now, at ingest later — see [03](03-CDR-Ingestion-and-3CX-Integration.md)):**

```python
# Wrong (silently drops 'ivr' and matches no 'NoAnswer')
cc = qs.filter(Q(to_type='Ivr') | Q(final_type='Ivr'))
missed = cc.filter(Q(final_type__isnull=True) | Q(reason_terminated='NoAnswer'))

# Right: case-insensitive type + the real answered signal
cc = qs.filter(Q(to_type__iexact='ivr') | Q(final_type__iexact='ivr'))
missed = cc.filter(time_answered__isnull=True)   # 461,602 unanswered of 1.49M
```

**R4/R6 fix — replace 24+21 loop scans and Python country counting with one grouped query:**

```python
from django.db.models.functions import TruncHour
hourly = (cc.annotate(h=TruncHour('call_time'))
            .values('h').annotate(n=Count('id')).order_by('h'))   # 1 query, not 24
```

---

## 3. UX Maturity Gap vs. Competitors

Across Variphy, Xima Chronicall, Tollring, Brightmetrics, Imagicle, Nectar and 3CX native, mature UC analytics products converge on seven pillars. The portal currently delivers a partial version of two of them.

| Pillar (industry benchmark) | Leaders | `connect.zentryc.com` today | Gap |
|---|---|---|---|
| Large prebuilt report library (50+) + cradle-to-grave drill-down | Xima 50+, per-leg ring/queue/hold/transfer | ~12 list/summary reports, no per-leg drill | **High** |
| Drag-drop widget dashboards (count/chart/table, per-user/shared/default, light/dark) | Variphy | Fixed server-rendered pages, one theme | **High** |
| Auto-refreshing TV-projectable wallboards | Variphy/Xima/Tollring/Brightmetrics | Channels wallboard exists but thin + broken `NoAnswer` filter | **Medium** |
| Scheduled reports (email/FTP, PDF/XLSX/CSV/HTML, hourly→monthly, window + timezone) | Variphy/Imagicle/Brightmetrics/3CX | **None** (no model, no worker) | **Critical** |
| Threshold alerts on KPIs | Brightmetrics/Tollring | None (see [08](08-Realtime-Alerts-and-Notifications.md)) | **High** |
| True ACD KPIs (SL, ASA, AHT, ACW, occupancy, abandonment) | All | Heuristic Ivr/NoAnswer counts only | **Critical** (owned by [05](05-Call-Center-Evaluation-Module.md)/[13](13-Call-Center-KPI-and-Metrics-Reference.md)) |
| Voice-quality dashboards (MOS/jitter/loss/latency) | Nectar/Variphy | QoS columns exist but **100% NULL** | **Medium** (needs new feed) |

Modern UI patterns to adopt: **widget drag-drop layouts, progressive disclosure** (collapsible sections, summary→detail drill, tabbed sub-views), **interactive time-series** (brush-to-zoom date range), **mobile-responsive**, **dark mode**, and **AI/anomaly callouts** (see the intelligence layer in [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md)).

---

## 4. Target Reporting Architecture

The goal is a **reporting service** that separates four concerns the current code conflates inside view functions: *query definition*, *aggregation/performance*, *rendering*, and *delivery*.

```
                 ┌──────────────────────────────────────────────┐
                 │            Report Definition (saved)          │
                 │  metrics · dimensions · filters · time window │
                 │  visualization · tenant · owner · sharing     │
                 └───────────────┬──────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────────┐
        ▼                        ▼                             ▼
┌───────────────┐      ┌──────────────────┐         ┌───────────────────┐
│ Query/Aggregate│     │   Renderer        │         │  Scheduler/Delivery│
│ engine (ORM +  │     │  HTML · CSV ·     │         │  (worker-driven)   │
│ rollup tables) │     │  XLSX · PDF       │         │  email · FTP · UI  │
└───────┬────────┘     └────────┬─────────┘         └─────────┬─────────┘
        │ reads                  │ produces                    │ runs on
        ▼                        ▼                             ▼
┌───────────────┐      ┌──────────────────┐         ┌───────────────────┐
│ indexed CDR +  │     │ one export module │         │ Celery/RQ worker   │
│ materialized   │     │ (replaces bespoke │         │ (NEW — none in prod│
│ rollups        │     │  per-view code)   │         │ today)             │
└───────────────┘      └──────────────────┘         └───────────────────┘
```

### 4.1 Report-builder + saved reports

A `ReportDefinition` lets users compose metrics/dimensions/filters and **save** them (per-user, shared, or tenant-default), instead of every report being a hard-coded view.

```python
class ReportDefinition(models.Model):
    company   = models.ForeignKey('accounts.Company', on_delete=models.CASCADE)
    owner     = models.ForeignKey('accounts.CustomUser', on_delete=models.CASCADE)
    name      = models.CharField(max_length=120)
    metrics   = models.JSONField()     # ["count","total_cost","service_level","asa"]
    group_by  = models.JSONField()     # ["queue","agent","day","hour","country"]
    filters   = models.JSONField()     # {"direction":"inbound","to_type":"ivr"}
    visualization = models.CharField(max_length=20, default="table")  # table|line|bar|donut
    sharing   = models.CharField(max_length=10, default="private")    # private|shared|default
```

Metric/dimension names resolve against a registry shared with [13](13-Call-Center-KPI-and-Metrics-Reference.md) so a "Service Level" tile and a "Service Level" report compute identically.

### 4.2 Server-side pagination & aggregation at scale

The current `Paginator` (`views.py:152,426,460…`) only slices the page; the underlying `QuerySet` still scans 1.49M unindexed rows. With ~2,000–3,800 calls/day across ~22 months, three changes are required:

1. **Index `(company_id, call_time)`** (R1) so range filters use an index, not a seq scan.
2. **Pre-aggregate** common rollups (per-hour/day/queue/agent volume, cost, answered/abandoned) into a **materialized rollup table** refreshed by the worker — dashboards read the rollup, not raw CDR. See [04](04-Data-Model-and-Database-Performance.md) for the rollup/partitioning design.
3. **Aggregate in the database, never in Python** — eliminate R6 (`Counter(countries)` over all rows) with `values('country').annotate(Count('id'))`.

### 4.3 Drill-down (cradle-to-grave)

Add a per-call detail view that, given a `correlation_id`, assembles all legs of a logical call (ring → queue → talk → transfer → hangup). The schema already carries `correlation_id`; once multi-leg ingestion lands (see [03](03-CDR-Ingestion-and-3CX-Integration.md) / [10](10-Multi-Vendor-and-Target-Architecture.md)) the same view renders Cisco/Teams/Webex/Zoom journeys identically.

### 4.4 Unified exports (CSV / Excel / PDF)

Replace the bespoke `openpyxl`/`reportlab` blocks duplicated across `views_reports.py` and `views.py` with **one** export module taking a `ReportDefinition` + result rows and emitting any format. Wire `import_export` `ModelResource` for CSV/XLSX; keep `reportlab` behind the PDF renderer. This kills R8 and guarantees branded, consistent output.

### 4.5 Scheduled reports that actually run

`ScheduledReport` references a `ReportDefinition` and is executed by the **new worker** ([08](08-Realtime-Alerts-and-Notifications.md), [12](12-Migration-Plan-and-Phased-Roadmap.md)). Feature parity target = Variphy/Imagicle:

```python
class ScheduledReport(models.Model):
    definition = models.ForeignKey(ReportDefinition, on_delete=models.CASCADE)
    recurrence = models.CharField(max_length=12)   # hourly|daily|weekly|monthly
    window     = models.CharField(max_length=20)   # prev_hour|prev_day|prev_week|custom
    timezone   = models.CharField(max_length=40, default='Asia/Riyadh')  # matches TIME_ZONE
    fmt        = models.CharField(max_length=8, default='pdf')           # pdf|xlsx|csv|html
    delivery   = models.JSONField()  # {"email":["ops@tenant"], "ftp":{...}}
    recipients = models.JSONField()  # resolved per-tenant, NOT hardcoded
```

> **Critical caveat:** the existing `UserQuota.send_quota_alert()` **hardcodes `recipient='khuram2025@gmail.com'`** (a developer address). Scheduled reports and alerts must resolve recipients from the tenant/extension owner. Fix recipient routing before promising "rich alerts/emails" — detailed in [08](08-Realtime-Alerts-and-Notifications.md) and [06-Billing-Quota-and-Fraud.md](06-Billing-Quota-and-Fraud.md).

---

## 5. Design System & Branding (`connect.zentryc.com`)

The portal already runs **Velzon/Bootstrap 5**, which ships the pieces we need; the work is to *expose and brand* them, not rebuild.

| Concern | Current | Target |
|---|---|---|
| Brand | Page titles still read "Velzon - Admin & Dashboard Template" (`base.html:6`); favicon generic | `connect.zentryc.com` wordmark, brand palette as Bootstrap CSS variables, branded login/PDF headers |
| Theme | `data-theme="default"`, single light theme (`base.html:3`) | **Light + dark** via Velzon `data-bs-theme`/customizer, persisted per user |
| Charts | Hand-coded `chart.js` `<canvas>` per template | Shared chart helper (consistent colors, tooltips, brush-to-zoom, dark-aware) |
| Forms | crispy **bootstrap4** vs BS5 page | crispy **bootstrap5** |
| Responsive | Velzon grid available, dashboards use fixed columns | Mobile-first breakpoints; wallboard has dedicated TV/kiosk layout |
| Accessibility | Color-only status, no ARIA on canvas | WCAG 2.1 AA: aria-labels on charts, color+icon status (not color alone), keyboard nav, contrast-checked palette |

### 5.1 Arabic / RTL + i18n

The tenants are MENA-based (`TIME_ZONE = Asia/Riyadh`, currency in SAR). The blocker is wiring, not assets:

- **`app-rtl.min.css` and `bootstrap-rtl.min.css` already exist in `/static/css`** — link them when the active locale is Arabic and set `<html dir="rtl" lang="ar">`.
- Add `django.middleware.locale.LocaleMiddleware`, define `LANGUAGES = [('en','English'),('ar','العربية')]` and `LOCALE_PATHS`, then wrap UI strings in `{% trans %}`/`gettext` (currently none are).
- Use an Arabic-friendly webfont (Tajawal/Cairo) and ensure numerals, dates (`Asia/Riyadh`), and SAR currency localize per locale.
- Exports (PDF via `reportlab`) need an RTL-capable font and right-aligned tables for Arabic output.

> **Finding (Medium):** RTL is "90% shipped, 0% switched on." A locale switcher in the topbar plus the two changes above is a high-visibility, low-effort win for MENA tenants.

---

## 6. Dashboard Redesigns (wireframes)

Four role-based dashboards, each showing **only the metrics that change behavior**, every number **paired with its target** and color-coded green/amber/red against a **configurable per-tenant `ThresholdPolicy`** (shared with the wallboard and alerts in [08](08-Realtime-Alerts-and-Notifications.md)).

### 6.1 Executive Overview

```
┌ connect.zentryc.com ▸ Executive Overview ───── [Smasco ▾] [Last 30d ▾] [☀/☾] [AR] ┐
│ ┌── Calls ──┐ ┌─ Answered % ─┐ ┌── Cost (SAR) ─┐ ┌── Avg Cost/Call ─┐ ┌─ Quota ─┐ │
│ │  68,420   │ │  69.1% ▲     │ │  41,232 SAR   │ │   0.60 SAR       │ │ 12 low  │ │
│ │  vs 64,1k │ │  tgt 80% ✗   │ │  ▲ 6% MoM     │ │                  │ │ alerts  │ │
│ └───────────┘ └──────────────┘ └───────────────┘ └──────────────────┘ └─────────┘ │
│ ┌─ Call volume (brush-to-zoom) ──────────────┐ ┌─ Top countries (cost) ─────────┐ │
│ │  ╱╲    ╱╲      ╱╲                           │ │ KSA ███████ Egypt ███ … (DB    │ │
│ │ ╱  ╲__╱  ╲____╱  ╲___  inbound│outbound     │ │ aggregate, not Python loop)    │ │
│ └────────────────────────────────────────────┘ └────────────────────────────────┘ │
│ ┌─ Tenants (Smasco / SAMNAN) side-by-side: calls · cost · answered% ─────────────┐ │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Call Control (operations)

```
┌ Call Control ───────────────────────── live · auto-refresh via /ws ───────────────┐
│ ┌ Active calls ┐ ┌ Blocked ext. ┐ ┌ Fraud incidents 24h ┐ ┌ Ingest health ───────┐│
│ │     7        │ │   3 (auto)   │ │   142 (18,361 total)│ │ socket :8000/:8005 ●  ││
│ └──────────────┘ └──────────────┘ └─────────────────────┘ └──────────────────────┘│
│ ┌ Live call grid (caller→callee, dur, dir, type) ─────────────────────────────────┐│
│ │ 0541116250 → 5490   00:09  inbound  ivr        ← canonicalized type             ││
│ └──────────────────────────────────────────────────────────────────────────────────┘
│  Cross-link: blockExternalCall enforcement → 06 · fraud rules → 06 · alerts → 08   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Billing (tenant)

```
┌ Billing ▸ SAMNAN ──────────────────────────────────── [Jun 2026 ▾] [Export ▾] ────┐
│ Cost by category (donut) │ Spend trend (line) │ Quota burn-down (per extension)     │
│ Tax (TaxRule) summary    │ Top spenders table │ Currency: SAR (multi-currency-ready)│
│ → invoicing/payments are NOT built yet — see 06-Billing-Quota-and-Fraud.md          │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### 6.4 Call Center (supervisor + agent)

Two role layouts; the formal ACD metric set and SLA thresholds are owned by [05](05-Call-Center-Evaluation-Module.md) and [13](13-Call-Center-KPI-and-Metrics-Reference.md). This doc owns the *presentation*.

```
┌ Call Center ▸ Supervisor (3CX San Francisco) ─ live wallboard ─ [project to TV] ──┐
│ ┌ Service Level ┐ ┌ Calls waiting ┐ ┌ Longest wait ┐ ┌ ASA ┐ ┌ Abandon % ┐        │
│ │ 78% (tgt 80%) │ │     4         │ │   02:11 ▲    │ │ 19s │ │  6.2% ✗   │ ← amber │
│ │  ▼ amber      │ │               │ │   red        │ │     │ │           │        │
│ └───────────────┘ └───────────────┘ └──────────────┘ └─────┘ └───────────┘        │
│ ┌ Agents (live state) ─────────────┐ ┌ Queues (live) ──────────────────────────┐  │
│ │ Aman   ● On-call  03:42          │ │ Sales   waiting 2  SL 81%  aband 4%     │  │
│ │ Sara   ○ Available                │ │ Support waiting 2  SL 74%  aband 9% ✗   │  │
│ │ Omar   ◐ Wrap-up  00:21          │ │  [silent monitor] [whisper] [barge]     │  │
│ └───────────────────────────────────┘ └─────────────────────────────────────────┘  │
│  NOTE: live state/longest-wait come from the Call Control feed → /ws, NOT the CDR. │
└───────────────────────────────────────────────────────────────────────────────────┘
```

> **Two data paths (do not conflate):** historical reporting (Service Level, ASA, abandonment trends) reads the **indexed/aggregated CDR**; the **live** wallboard (longest/oldest wait, agent state) reads a **live queue feed** over the existing Channels/Redis/daphne path — never the CDR table (it only writes at call end and lacks live state). Detailed in [05](05-Call-Center-Evaluation-Module.md) and [08](08-Realtime-Alerts-and-Notifications.md).

---

## 7. Phased Recommendations

| Phase | Deliverable | Severity / Effort | Cross-ref |
|---|---|---|---|
| **0 (days)** | Add `(company_id, call_time)` index (R1); fix `to_type__iexact` + `time_answered IS NULL` (R2/R3); collapse 24+21 loops → 1 grouped query (R4); kill `Counter` Python loop (R6) | Critical / S–M | [04](04-Data-Model-and-Database-Performance.md), [05](05-Call-Center-Evaluation-Module.md) |
| **1** | Turn on dark mode + RTL/i18n (assets already shipped); crispy → bootstrap5; brand `connect.zentryc.com`; unify exports (R8/R9/R10) | High / M | this doc |
| **2** | Rollup tables + reporting service; report-builder + saved reports; cradle-to-grave drill-down | High / L | [04](04-Data-Model-and-Database-Performance.md), [13](13-Call-Center-KPI-and-Metrics-Reference.md) |
| **3** | Worker-backed scheduled reports (email/FTP, PDF/XLSX/CSV, recurrence/window/timezone) + fix recipient routing | High / L | [08](08-Realtime-Alerts-and-Notifications.md), [12](12-Migration-Plan-and-Phased-Roadmap.md) |
| **4** | Widget drag-drop role dashboards (exec/call-control/billing/call-center) + live wallboard rebuild + QoS dashboards once a quality feed exists | Medium / XL | [05](05-Call-Center-Evaluation-Module.md), [10](10-Multi-Vendor-and-Target-Architecture.md) |

The consolidated, prioritized backlog lives in [11-Gap-Analysis-and-Feature-Backlog.md](11-Gap-Analysis-and-Feature-Backlog.md); the sequencing and rollback plan in [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md). This set supersedes the older `/home/ubuntu/3CX/enhancement/*.md` business-strategy docs for engineering purposes; the "IPT Insight/Contact" product framing there maps onto Phases 2–4 here, but the technical specification is owned by this document set.
