# connect.zentryc.com — Architecture, Evaluation & Migration Documentation

This is the engineering source-of-truth documentation set for the **connect.zentryc.com** 3CX call-accounting / billing / call-control / call-center analytics platform. It is a complete, evidence-based audit of the current system, a set of design and research findings, and a phased plan to evolve it into an intelligent, vendor-neutral CX analytics platform.

**Produced:** 2026-06-05. **Method:** a deep read of the live codebase (`/home/ubuntu/3CX/cdr`), read-only queries against the production `cdr` PostgreSQL database, and external research into modern 3CX integration, contact-center KPI standards, and competitor/multi-vendor benchmarks. **Every load-bearing number and `path:line` citation in this set was verified against the running system**, not assumed.

---

## How to read this set

| If you are… | Start here | Then |
|---|---|---|
| An executive / stakeholder | [01-Executive-Summary.md](01-Executive-Summary.md) | [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md) |
| An engineering lead planning the work | [11-Gap-Analysis-and-Feature-Backlog.md](11-Gap-Analysis-and-Feature-Backlog.md) | [12](12-Migration-Plan-and-Phased-Roadmap.md) → the domain docs |
| Working on the call-center module (priority) | [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md) | [13-Call-Center-KPI-and-Metrics-Reference.md](13-Call-Center-KPI-and-Metrics-Reference.md) |
| Working on ingestion / 3CX / multi-vendor | [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md) | [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md), [04](04-Data-Model-and-Database-Performance.md) |
| Hardening / compliance | [09-Security-and-Compliance.md](09-Security-and-Compliance.md) | [02](02-Current-System-Architecture-Audit.md) |

## Table of contents

| # | Document | What it covers |
|---|----------|----------------|
| 00 | **README** (this file) | Index, method, install instructions |
| 01 | [Executive Summary](01-Executive-Summary.md) | The verified headline findings, target vision, plan-at-a-glance |
| 02 | [Current System Architecture Audit](02-Current-System-Architecture-Audit.md) | Process/deployment topology, app map, data flows, cross-cutting tech debt |
| 03 | [CDR Ingestion & 3CX Integration](03-CDR-Ingestion-and-3CX-Integration.md) | The socket pipeline, its failure modes, modern 3CX options (DB pull / XAPI / Call Control), and an ingestion redesign |
| 04 | [Data Model & Database Performance](04-Data-Model-and-Database-Performance.md) | Schema, the missing `call_time` index, partitioning/rollups, new ACD entities, migration-safe DDL |
| 05 | [Call Center Evaluation Module](05-Call-Center-Evaluation-Module.md) | **Priority.** Why it under-reports, a proper ACD model, the agent/supervisor KPI suite, wallboard/QA designs, build order |
| 06 | [Billing, Quota & Fraud](06-Billing-Quota-and-Fraud.md) | Rating maturity, the quota race + dead alert code, fraud rules stuck in shadow mode, the path to a billing SaaS |
| 07 | [Reporting, Dashboards & UI/UX](07-Reporting-Dashboards-and-UI-UX.md) | Report catalog, UX gaps, target reporting architecture, design system, RTL/i18n |
| 08 | [Real-time, Alerts & Notifications](08-Realtime-Alerts-and-Notifications.md) | The wallboard, why async never fires, an event-driven alert/escalation engine, worker deployment |
| 09 | [Security & Compliance](09-Security-and-Compliance.md) | Production hardening, tenant isolation, RBAC, audit logging, PII/PDPL/GDPR |
| 10 | [Multi-Vendor Strategy & Target Architecture](10-Multi-Vendor-and-Target-Architecture.md) | Vendor-neutral canonical model, the adapter contract, the event-driven target, the AI layer |
| 11 | [Gap Analysis & Prioritized Backlog](11-Gap-Analysis-and-Feature-Backlog.md) | **The master backlog.** Top-10 critical fixes, capability gap matrix, epics → stories (P0–P3) |
| 12 | [Migration Plan & Phased Roadmap](12-Migration-Plan-and-Phased-Roadmap.md) | P0–P6 phases with goals, exit criteria, risks, rollback, team shape |
| 13 | [Call Center KPI & Metrics Reference](13-Call-Center-KPI-and-Metrics-Reference.md) | Precise definitions/formulas for every metric and how to compute each from CDR data |

## Ground-truth snapshot (verified 2026-06-05)

- **Stack:** Django 5.0.7 monolith; nginx → gunicorn (web) + Daphne (WebSocket); raw-TCP `socket_server` ingests 3CX CDRs; PostgreSQL 16 + Redis. **No Celery/worker and no app cron run** — async/scheduled features do not fire.
- **Data:** 1,492,192 call records, **100% `source_pbx='3cx'`**. Tenants: **Smasco** (port 8000), **SAMNAN** (port 8005). ~2–4k calls/day, span 2024-07 → 2026-06.
- **The defining bug:** the call-center dashboard and the real-time wallboard filter on `to_type='Ivr'` and `reason_terminated='NoAnswer'` — but the data turned lowercase after a 3CX upgrade and `NoAnswer` matches **0 rows**, so both have shown wrong/empty numbers for ~6 months. This is the cause of the open `issues.txt` complaint. Full evidence in [05](05-Call-Center-Evaluation-Module.md).

## Relationship to prior documentation

This set **supersedes, for engineering purposes**, the earlier material:

- `/home/ubuntu/3CX/enhancement/` — a 2026-05-12 **business/market-strategy** set (product lines "IPT Bill/Insight/Contact", pricing, MENA strategy, 18-month roadmap). Still useful for go-to-market framing; this set is the engineering counterpart and reconciles what of it actually shipped (mostly schema/plumbing, not wired-up features).
- `/home/ubuntu/3CX/documentation/` — sparse legacy notes (`features.md`, `mail_doc.md`, `ui.md`); subsumed here.

## Installing this set into the project repo

This set was authored in `/home/net/zentryc/Documentation/` because the repository at `/home/ubuntu/3CX` is owned by the `ubuntu` user and the authoring session runs as `net` without sudo. To place it in the project's `Documentation/` folder, run (you will be prompted for a password):

```bash
sudo mkdir -p /home/ubuntu/3CX/Documentation
sudo cp /home/net/zentryc/Documentation/*.md /home/ubuntu/3CX/Documentation/
sudo chown -R ubuntu:ubuntu /home/ubuntu/3CX/Documentation
```

> Tip: in this Claude Code session you can run that directly by typing `!` followed by the command.

## A note on conventions

Findings are tagged **Critical / High / Medium / Low** (blast radius if unaddressed) and **S / M / L / XL** effort (S ≈ <1 day, M ≈ days, L ≈ 1–2 weeks, XL ≈ a month+). Recommendations are framed **current → target**. Documents cross-link by exact relative filename rather than duplicating each other; [11](11-Gap-Analysis-and-Feature-Backlog.md) is the single backlog that feeds the roadmap in [12](12-Migration-Plan-and-Phased-Roadmap.md).
