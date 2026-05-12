# IPT Portal — Enhancement Program

**Owner:** Khurram (khuram2025@gmail.com)
**Last updated:** 2026-05-12
**Working dir:** `/home/ubuntu/3CX/enhancement/`

This folder contains the complete strategic and tactical plan for evolving the current 3CX-only billing portal (`iptportal.channab.com`) into a **multi-PBX cloud billing + AI contact-center platform** for MENA and beyond.

---

## 📂 Folder map

```
enhancement/
├── README.md                          ← you are here
├── 00-executive-summary.md            ← 1-page TL;DR for leadership
├── 01-current-system-audit.md         ← what we have today (capabilities, models, gaps)
├── 02-gap-analysis.md                 ← what's missing vs. market expectations
├── 03-competitor-analysis.md          ← matrix of 20+ competitors, strengths, weaknesses
├── 04-market-research.md              ← TAM, trends, pricing benchmarks
├── 05-business-opportunities.md       ← new revenue lines & verticals
├── 06-feature-catalog.md              ← 80+ feature ideas, scored & prioritized
├── 07-roadmap.md                      ← 18-month phased plan
├── 08-pricing-strategy.md             ← tiers, packaging, GTM motions
├── 09-mena-strategy.md                ← KSA/UAE/Egypt-specific moat
├── 10-technical-architecture.md       ← target architecture & migration path
│
├── plans/
│   ├── phase1-foundations.md          ← months 0-3
│   ├── phase2-multi-pbx.md            ← months 3-6
│   ├── phase3-ai-cx.md                ← months 6-12
│   └── phase4-platform.md             ← months 12-18
│
├── tasks/
│   ├── phase1-tasks.md                ← granular tickets, est. effort
│   ├── phase2-tasks.md
│   ├── phase3-tasks.md
│   └── phase4-tasks.md
│
└── research/
    ├── competitors/                   ← deep-dive per competitor
    │   ├── variphy.md
    │   ├── tollring.md
    │   ├── imagicle.md
    │   ├── portabilling-timelybill.md
    │   └── xima-cloudtalk-others.md
    ├── integrations/                  ← how to ingest data per PBX
    │   ├── cisco-cucm.md
    │   ├── microsoft-teams.md
    │   ├── webex-calling.md
    │   ├── zoom-phone.md
    │   └── asterisk-freepbx.md
    └── verticals/                     ← market-segment research
        ├── banking-sama.md
        ├── healthcare.md
        ├── ai-voice-agents.md
        ├── fraud-detection.md
        ├── call-quality-monitoring.md
        ├── wfm.md
        ├── predictive-dialer.md
        └── compliance-pci-gdpr.md
```

---

## 🎯 The thesis (one paragraph)

The current product is a **3CX-only call accounting + chargeback tool with strong multi-tenant rate-card and quota engines**. The market wants **a unified billing & analytics SaaS that ingests CDRs from 3CX + Cisco CUCM + MS Teams + Webex + Zoom + SIP trunks, then layers AI (transcription, sentiment, QA), wallboards, fraud detection, WFM, and omnichannel** — sold per-tenant at $15-$50/user/mo. **No vendor owns the MENA region with native Arabic, SAR/AED billing, and CITC/SAMA-aware compliance.** That's the wedge.

---

## 🚀 Reading order

If you have **5 minutes:** read `00-executive-summary.md`
If you have **30 minutes:** add `02-gap-analysis.md`, `03-competitor-analysis.md`, `07-roadmap.md`
If you're **starting work:** open `tasks/phase1-tasks.md` — every ticket has acceptance criteria and effort estimate
If you're **pitching investors / partners:** use `00-executive-summary.md` + `04-market-research.md` + `08-pricing-strategy.md`
If you're **engineering:** start with `10-technical-architecture.md`

---

## ✅ Status of this plan

| Document | Status |
|---|---|
| Executive summary | ✅ Drafted |
| System audit | ✅ Drafted |
| Gap analysis | ✅ Drafted |
| Competitor analysis | ✅ Drafted |
| Market research | ✅ Drafted |
| Business opportunities | ✅ Drafted |
| Feature catalog | ✅ Drafted |
| Roadmap | ✅ Drafted |
| Pricing strategy | ✅ Drafted |
| MENA strategy | ✅ Drafted |
| Technical architecture | ✅ Drafted |
| Phase 1-4 plans | ✅ Drafted |
| Phase 1-4 task lists | ✅ Drafted |
| Competitor deep-dives | ✅ Drafted |
| Integration research | ✅ Drafted |
| Vertical research | ✅ Drafted |

All sources are linked inline within each document.
