# Phase 4 — Platform & Adjacent Revenue (Months 12-18)

**Theme:** Become the platform, not a tool. Expand into AI voice agents, dialers, deep CRM integrations, vertical bundles, regulated industries.

---

## Goals

1. Deep CRM + help-desk integrations (Salesforce, HubSpot, Zoho, Bitrix24, Odoo, Dynamics, Pipedrive, Zendesk, Freshdesk, Intercom)
2. Launch AI voice agent product (inbound IVR + outbound campaigns)
3. Predictive / power dialer for BPO market
4. DID / number inventory + carrier integration
5. SOC 2 Type II + ISO 27001 + PCI DSS
6. Multi-region data residency (KSA, UAE, EU)
7. Cross-tenant benchmarking
8. Vertical bundles (Bank, Health, Hospitality, Government)

## Workstreams

### W39 — CRM connectors (3 backend + 1 frontend, 12 weeks split)
- Salesforce (managed package on AppExchange)
- HubSpot (marketplace app)
- Zoho CRM (extension)
- Bitrix24 (REST API)
- Odoo (module)
- Microsoft Dynamics 365 (Power Platform connector)
- Pipedrive (marketplace app)
- Each: click-to-call, screen pop, call logging, contact sync, recording link

### W40 — Help-desk integrations (1 backend, 4 weeks)
- Zendesk (ticket sync, recording attachment, agent context)
- Freshdesk
- Intercom

### W41 — AI voice agent product (3 ML + 2 backend + 1 frontend, 16 weeks)
- LLM-driven dialog management (GPT-4 / Claude / fine-tuned local)
- Multi-language: Arabic (MSA + dialects), English, Urdu, Hindi, Tagalog
- Inbound IVR replacement: intent classification, slot filling, fulfillment
- Outbound campaigns: surveys, appointment confirmations, debt collection
- FAQ deflection bot
- Appointment booking (calendar API integration)
- Voice-to-CRM (auto-create records from conversation)
- Bot → human handoff with full context
- Custom voice cloning (premium)
- Per-minute billing + minute-cap enforcement

### W42 — Predictive / power dialer (2 backend + 1 frontend, 10 weeks)
- Predictive dialer (ratio-based, learns from connect rates)
- Power dialer (1:1, agent-paced)
- Preview dialer
- Answering machine detection (AMD)
- Voicemail drop
- DNC (Do Not Call) list management + scrubbing
- Time-zone aware dialing
- Abandonment rate enforcement (<3% per TCPA)
- Campaign management dashboard
- Lead list management + dispositioning
- Agent screen pop with lead context

### W43 — DID / number management (2 backend + 1 frontend, 8 weeks)
- DID inventory (numbers owned, assigned, available)
- Port-in / port-out workflows (carrier coordination)
- Vanity number search
- Number assignment to extensions / queues / IVR
- Number history (who owned it, when)
- Carrier integration (DIDWW, Voxbone/Bandwidth, local KSA carriers)

### W44 — Carrier / SBC integration (1 backend, 6 weeks)
- SBC visibility (Asterisk/Kamailio/Sansay log ingestion)
- Carrier rate-card sync (auto-import from carriers' portals)
- Margin analysis per carrier
- Carrier QoS comparison
- Auto-failover routing rules

### W45 — Multi-entity billing + CPQ (1 backend + 0.5 frontend, 6 weeks)
- Parent/child organization model
- Consolidated invoicing across child orgs
- Inter-company chargeback
- CPQ (Configure-Price-Quote) workflow for sales

### W46 — Cross-tenant benchmarking (0.5 ML + 0.5 frontend, 4 weeks)
- Anonymized cross-tenant aggregations
- Peer benchmarks: "Your AHT is 15% higher than industry median for banking"
- Opt-in for customer participation
- Privacy guarantees (k-anonymity)

### W47 — Real-time RTP monitoring (1 backend, 4 weeks)
- Pcap-style capture from SBC
- Live MOS calculation
- One-way audio detection
- Codec mismatch alerts

### W48 — Multi-region data residency (1 SRE + 1 backend, 8 weeks)
- Terraform per region
- Tenant region attribute → routing at edge (CloudFront / Route 53)
- Per-region control plane (small) replicated; data plane fully isolated
- Migration tool (move tenant from region A → B)

### W49 — SOC 2 Type II + ISO 27001 + PCI DSS (1 compliance, ongoing)
- Type I obtained in Phase 3; Type II requires 6+ months of evidence
- ISO 27001 certification audit
- PCI DSS attestation (for recording bundle handling card data)
- Continuous compliance monitoring (Drata, Vanta, Secureframe)

### W50 — Multi-channel WFM + advanced (1 backend + 0.5 frontend, 6 weeks)
- Multi-channel forecasting (voice + chat + email weighted)
- What-if scenario planning
- Calendar sync (Google / Outlook)
- Schedule swap workflow
- Intraday re-forecast

### W51 — Vertical bundles (1 product manager + 1 backend per bundle, 4 weeks each)
- **IPT Bank**: pre-configured for KSA banking
  - SAMA 10-yr retention enabled
  - PCI redaction enabled
  - Arabic + English IVR templates for banking flows
  - SAMA-compliant audit reports
  - FATF screening integration (sanctions list)
- **IPT Health**: clinic / hospital
  - Appointment booking bot
  - After-hours triage IVR
  - Telemedicine integration (Zoom/Teams meeting links)
  - Patient privacy (PII redaction)
- **IPT Hospitality**: hotels
  - PMS integration (Opera, Mews, Cloudbeds)
  - Guest service routing (multi-language)
  - VIP guest detection
- **IPT Government**: govt entities
  - Arabic-first UI
  - Accessibility (WCAG 2.1 AA)
  - Citizen survey bot
  - KSA data residency (in-Kingdom)

### W52 — Generic SQL / data warehouse export (0.5 backend, 2 weeks)
- Read-only Postgres replica per tenant (or shared with row-level security)
- BigQuery / Snowflake / Redshift Fivetran-style connector
- Documentation for data team consumers

### W53 — Avaya / Mitel / RingCentral / Vonage / 8x8 / NEC adapters (2 backend, 12 weeks)
- One adapter per ~2 weeks
- Prioritize by customer demand

### W54 — ML-based fraud anomaly detection (1 ML, 4 weeks)
- Train per-tenant baseline of normal call patterns
- Anomaly score per call
- Auto-tune thresholds
- Better than rule-based for novel fraud

### W55 — DLP for recordings (0.5 ML + 0.5 backend, 4 weeks)
- Detect sensitive info shared verbally that shouldn't be (passwords, full SSN)
- Alert security team
- Auto-redact post-detection

---

## Phase 4 timeline (24 weeks ≈ 6 months)

Roughly 5-6 parallel workstreams at any time. CRM + AI voice agent + dialer + DID are the biggest bets.

| Month | Highlight |
|---|---|
| M13 | W39 CRM (Salesforce + HubSpot first) + W41 AI voice agent start + W43 DID start + W49 SOC 2 Type II evidence collection |
| M14 | W39 (Zoho + Bitrix24 + Odoo) + W41 continues + W42 predictive dialer start + W43 ship |
| M15 | W40 help-desk + W41 continues + W42 continues + W44 carrier + W48 multi-region start |
| M16 | W39 (Dynamics + Pipedrive) + W41 ship inbound IVR + W42 ship + W45 multi-entity + W46 benchmarking |
| M17 | W41 ship outbound campaigns + W47 RTP + W48 multi-region ship + W50 advanced WFM + W51 IPT Bank + IPT Health |
| M18 | W51 IPT Hospitality + IPT Government + W52 SQL export + W53 (Avaya + Mitel start) + W54 ML fraud + W49 audits complete |

---

## Engineering allocation (peak)

| Role | HC | Notes |
|---|---|---|
| Backend | 5 | spread across CRM, dialer, DID, carrier, region |
| Frontend | 3 | CRM widgets, dialer UI, vertical templates |
| Mobile | 1 | maintenance + new features |
| ML/AI | 2 | voice agent dialog + fraud anomaly + benchmarking |
| SRE / DevOps | 2 | multi-region, scale |
| Compliance | 1 | SOC 2 Type II + ISO 27001 + PCI |
| Product Manager | 1 | vertical bundles |

→ ~14-15 FTE peak

---

## Acceptance criteria

| Criterion | Target |
|---|---|
| Enterprise customers using SOC 2 attestation in procurement | 5+ |
| Minutes/month on AI voice agent product | 1M+ |
| Customers running predictive dialer campaigns | 10+ |
| Banks live on SAMA-bundle + KSA data residency | 3+ |
| Total ARR (cumulative all customers) | SAR 10M+ |
| CRM-integrated customer count | 30+ |

---

## Risks

| Risk | Mitigation |
|---|---|
| Salesforce AppExchange security review takes 6+ months | Start week 1; have Plan B private connector for early customers |
| AI voice agent latency too high for production | Use streaming STT + LLM; keep latency budget <800ms for natural conversation |
| Predictive dialer regulatory changes (TCPA-like in KSA?) | Build flexible compliance module; consult local counsel |
| DID port-in delays from local carriers | Set realistic SLA expectations; cushion in contract |
| Multi-region complexity blows up dev velocity | Phase per region; KSA + UAE first, EU later |
| SOC 2 Type II audit findings | Use Drata/Vanta to monitor continuously, fix as you go |
| Vertical bundles dilute focus | Limit to 4; only build if 3+ committed customers per vertical |
