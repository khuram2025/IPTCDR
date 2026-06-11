# Implementation Status

Live tracker of roadmap delivery (see `12-Migration-Plan-and-Phased-Roadmap.md`).
Updated as phases are built + verified on the running system (tenant: Smasco, id=2).

Legend: ✅ done & verified · 🟡 partial/scaffolded · ⛔ blocked (needs external creds/system) · ⬜ not started

## P0 — Stabilize & Secure
- ✅ P0.1 Flagship case-bug hotfix
- ✅ P0.2 `call_time` composite index
- ✅ P0.3 Fix alert recipient
- ✅ P0.4 Lock down socket (per-tenant IP allowlist, UI-managed)
- ✅ P0.5 Production security baseline (env secrets, DEBUG off, ALLOWED_HOSTS)
- ✅ P0.6 Celery worker + beat + Redis broker
- ✅ P0.7 Tame print/signal storm

## P1 — Canonical Ingest & ACD Entity Layer
- ✅ P1.1 Canonical CallRecord superset (derived ACD columns)
- ✅ P1.2 ACD entity layer (Queue/Agent/State/Disposition/CallLeg/Recording)
- ✅ P1.3 Queue performance connector — **via 3CX V20 XAPI** (Postgres firewalled)
- ✅ P1.3-ext Abandoned-call + agent-in-queue reports (true abandonment + occupancy)
- ✅ P1.7 Hardened socket fallback (recv loop, IP allowlist)
- 🟡 P1.4/P1.5/P1.6/P1.8 partials (enrichment task, normalization, backfill) — core in place

## P2 — Call-Center Evaluation Module
- ✅ P2.2 KPI engine (real_queue_kpis, agent_productivity, abandonment)
- ✅ P2.3 ThresholdPolicy (per-tenant/per-queue)
- ✅ P2.4 Supervisor wallboard (live, 3CX ActiveCalls feed, Redis-throttled)
- ✅ P2.5 Agent dashboard (per-agent ACD drill-down vs targets)
- ✅ P2.6 SLA-breach alerts (tiered amber/red, QueueAlert, daily beat)

## P3 — Reporting, Dashboards & UX
- ✅ P3.1 Scheduled-report engine (4 types × csv/xlsx/pdf/html, beat, UI)
- ✅ P3.1-edges Email hardening (EMAIL_TIMEOUT=20) + report-file retention task/beat
- ✅ P3.2 Report catalog (7 report types) + per-call drill-down (timeline/QoS/related). Multi-leg cradle-to-grave needs correlation_id (0% populated on socket feed) → DB-pull/P5; honestly noted in UI.
- 🟡 P3.3 Design system: light/dark mode ✅ (Velzon theme + layout.js persistence, verified). Drag-drop widget dashboards deferred (large SPA frontend).
- ✅ P3.4 RTL + i18n foundation: LocaleMiddleware + LANGUAGES(en/ar) + set_language + topbar switcher; Arabic flips layout to dir=rtl (verified). Full Arabic string catalog deferred.
- ✅ P3.5 Materialized rollups (CallDailyRollup, nightly beat, reconciles exactly; dashboard rollup-backed)

## P4 — Billing-Grade & Alert Rules
- ✅ P4.1 Invoicing & payments — Invoice/InvoiceLineItem/Payment models, generate_invoice service, command, admin. Verified: subtotal reconciles to summed total_cost; partial→full payment flips to paid; idempotent on paid. Gateway integration deferred (needs sandbox creds).
- ✅ P4.2 Multi-currency + tax wiring — invoice uses Company.currency; TaxRule resolved by company override→country_code w/ effective dating; verified SAR + 15% KSA VAT.
- ✅ P4.3 Quota correctness: select_for_update confirmed; UserQuota.is_blocked + should_block(); enforce_quota_state task (idempotent transitions, off hot path via on_commit, parameterized blockExternalCall, gated by QUOTA_ENFORCEMENT_ENABLED for safety). Verified block/unblock logic.
- ✅ P4.4 Alert rules engine — AlertRule/AlertEvent (notifications app), multi-source (fraud/acd_sla/quota), severity filter, multi-channel dispatch (email real; SMS/WhatsApp pluggable stubs), time-based escalation, beat task (inert until a rule exists), bounded per run. Verified firing on the 18,361 fraud incidents + idempotent drain + cleanup. SMS/WhatsApp gateway wiring deferred (needs provider creds).

## P5 — Multi-Vendor Adapters
- ✅ P1.4/P5 CdrSource adapter interface — acd/sources/base.py (CANONICAL_FIELDS + fetch→normalize→canonical contract). Vendor quirks isolated per subclass.
- 🟡 P5.1 CiscoCucmCdrSource — acd/sources/cucm.py: CDR+CMR parsing → canonical (globalCallID pair → correlation_id; CMR QoS jitter/latency/loss/MOS joined). Verified on synthetic rows. Live SFTP poller (fetch()) ⛔ needs a CUCM SFTP drop.
- ✅ P5.2 Version/edition detection — acd/sources/detect.py: 3CX major-version via XAPI SystemStatus → edition + ingest_transport tag. Verified (Smasco=3cx-v20→xapi, SAMNAN=socket).
- ⛔ P5.3 Cloud adapters (Teams/Webex/Zoom) — needs vendor API creds + tenants.
- 🟡 P5.4 Public API / partner enablement — DRF/ApiKey surface exists; webhook maturation not yet built.

## P6 — AI & QA — ⛔ needs call recordings + an LLM API key
- ⛔ P6.1 Recording ingestion + transcription (Recording model exists; 3CX CallLogData exposes RecordingUrl/Transcription/SentimentScore — wire when recordings + transcription provider available)
- ⛔ P6.2 Sentiment + summaries (use the claude-api reference for the LLM calls)
- ⛔ P6.3 QA automation · ⛔ P6.4 Forecasting · 🟡 P6.5 CSAT/NPS surveys (IVR/CFD ingest API, dashboards, rollups — recording playback deferred)

## Public marketing site (SEO) — 2026-06-06
- ✅ Rebuilt the public site as **Zentryc** (was generic "Channab"). Self-contained modern design system (Inter font, indigo/violet+cyan palette, gradients, responsive) in `templates/public/base.html`; Remix Icon CDN.
- ✅ Pages: Home (hero + live-dashboard mock + trust strip + feature highlights + how-it-works + platform modules + CTA), Features (all modules grouped: analytics/realtime/reporting/billing/security), Pricing (Starter/Pro/Enterprise + FAQ + Product JSON-LD), About, Contact (working form → best-effort lead email). Views in `cdr3cx/public_views.py`; routes `/ /features/ /pricing/ /about/ /contact/`.
- ✅ SEO: per-page title/description/keywords/canonical, Open Graph + Twitter cards, JSON-LD (Organization + SoftwareApplication + Product), semantic H1/H2, `/robots.txt` + `/sitemap.xml` (5 URLs). All pages verified HTTP 200.

---
## Summary (autonomous run, 2026-06-06)
**Fully delivered + verified:** P0 (all), P1 core + P1.3/P1.4, P2 (all), **P3 (all — 3.1/3.2/3.5 full; 3.3 light-dark; 3.4 RTL+i18n foundation)**, **P4 (all — invoicing, currency/tax, quota enforcement, alert-rules engine)**, **P5.2 + CdrSource interface**.
**Scaffolded/partial (code in place, full delivery needs external systems):** P3.3 drag-drop widgets, P5.1 live CUCM ingest, P5.4 webhooks.
**Blocked on external creds/systems:** P5.3 cloud adapters, all of P6 (recordings + LLM key), live email delivery (SMTP password) + SMS/WhatsApp gateways.

---
_Files touched live in `/home/ubuntu/3CX/cdr`; services: gunicorn/daphne/socket_server/celery/celery-beat._
