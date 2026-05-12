# Executive Summary

## The product today
A multi-tenant **3CX-only** Django web app that:
- Ingests CDRs in real time via socket + HTTP
- Computes per-call cost using configurable rate cards (mobile / national / intl / local)
- Enforces per-extension quotas (auto-disable on overage) — a real differentiator
- Generates dashboards, top-extension reports, country breakdowns, sales-call reports
- Just shipped a basic call-center module (IVR stats, agent perf, missed calls, callbacks)
- Supports superadmin / company_admin / user roles with custom per-company roles
- Currency hard-coded to SAR; UI English-only; no public website beyond a new landing page

## The market opportunity
- **Speech analytics market:** $3.2B by 2026
- **VoIP billing market:** dominated by US/EU vendors (PortaBilling, TimelyBill, Variphy, Tollring, Imagicle); none have native MENA presence
- **Cisco no longer ships a comprehensive call-accounting suite** — partners fill the gap (Variphy is the leader)
- **Microsoft Teams** is now the fastest-growing UC platform — third-party reporting (Variphy, Tollring iCall Suite, Teams PowerPack, ISI Analytics) is a hot category
- **AI voice agents:** $0.05–0.25/min, $350/mo per 1,000 min — proven price point
- **MENA-specific requirements** (Arabic RTL, SAR/AED, VAT 15%, CITC/SAMA, Mada/HyperPay/PayTabs, 10-year SAMA recording retention) are unmet by global vendors

## The strategic pivot

| From | To |
|---|---|
| 3CX-only billing tool | Multi-PBX cloud billing + analytics + AI CCaaS |
| Internal cost-tracker | True billing SaaS (invoices, payments, dunning) |
| Static dashboards | Real-time wallboards + AI insights |
| Voice-only | Omnichannel (voice + WhatsApp + chat + email) |
| Single product | 3 product lines: **IPT Bill**, **IPT Insight**, **IPT Contact** |

## 3 product lines, sold standalone or bundled

1. **IPT Bill** — Convergent rating, invoicing, taxes, fraud, multi-PBX adapters, payment gateways
2. **IPT Insight** — Wallboards, custom report builder, KPIs, exports, scheduled reports
3. **IPT Contact** — Call recording, transcription, sentiment, QA scorecards, WFM, omnichannel

## Pricing (suggested SAR/mo per tenant)

| Tier | Target | Price |
|---|---|---|
| Starter | <50 ext | 499 |
| Business | 50-250 ext | 1,499 |
| Pro | 250-1,000 ext | 3,999 |
| Enterprise | 1,000+ | Custom |
| White-label / Reseller | MSP partners | rev-share |

Plus usage add-ons: AI minutes, recording storage, SMS/WhatsApp messages, extra PBX adapters.

## The 30-day plan

1. Stop committing `venv/`, `__pycache__`, `debug.log` (`.gitignore` + `git rm --cached`)
2. Refactor `CallRecord` to a vendor-neutral schema with `source_pbx` field (unblocks all PBX adapters)
3. Add multi-currency support per company (unblocks first non-KSA sale)
4. Ship a real-time wallboard via Django Channels (best demo upgrade)
5. Build the toll-fraud alert engine — quickest new revenue line, ~2 weeks of work
6. Wire HyperPay or PayTabs + PDF invoice generator → become a real billing SaaS
7. Document a public REST API (DRF + OpenAPI) — unblocks every future integration

## The 18-month picture

| Quarter | Outcome |
|---|---|
| Q1 (M0-3) | Foundations: multi-currency, RTL Arabic, wallboards, fraud alerts, invoices, payments, public API |
| Q2 (M3-6) | Multi-PBX: Cisco CUCM, MS Teams, Webex, Zoom, generic SIP adapters; LCR; reseller tier |
| Q3-Q4 (M6-12) | AI/CX: call recording, Whisper transcription (Arabic+English), sentiment, QA, WFM-lite, omnichannel, mobile app |
| Q5-Q6 (M12-18) | Platform: CRM integrations (Salesforce/HubSpot/Zoho), AI voice agents, predictive dialer, DID inventory, SOC 2 readiness |

## Bet size & expected outcome

- **Engineering:** 2-4 FTE for 18 months
- **Revenue model:** SaaS ARR from per-tenant subscriptions + usage
- **Realistic 18-month ARR target:** SAR 5–15M depending on partner channel signups (10 MSPs × 50 customers × ~SAR 1,500/mo avg)
- **Strategic outcome:** become the default UC analytics & billing platform for MENA mid-market and the first call most enterprises make when shopping for a Variphy/Tollring alternative

→ See `07-roadmap.md` for the full 18-month plan.
→ See `tasks/phase1-tasks.md` to start work today.
