# Phase 2 — Multi-PBX & White-Label (Months 3-6)

**Theme:** Stop being "3CX-only." Become "any UC platform." Open the partner channel.

---

## Goals

1. Cisco CUCM, Microsoft Teams, Webex Calling, Zoom Phone, generic SIP adapters live
2. White-label / reseller tier with branded customer portals
3. LCR engine + multi-carrier rate-card import
4. Prepaid wallet + hybrid billing models
5. Customizable wallboard widgets (drag-drop)

## Workstreams

### W11 — PBX adapter framework (1 backend, 3 weeks)
- Pluggable adapter ABC + registry
- Adapter test harness with sample CDR fixtures
- Adapter-specific config UI (per tenant)
- Health checks per adapter
- Documentation for ISVs/partners to write their own adapters

### W12 — Cisco CUCM adapter (1 backend, 3 weeks)
- SFTP listener (CUCM pushes CDR/CMR files)
- CSV parser per CUCM version (12.x, 14.x, 15.x)
- Map CUCM fields → NormalizedCdr
- Setup guide for customers (configure CUCM Billing Application Server)
- See `research/integrations/cisco-cucm.md`

### W13 — Microsoft Teams adapter (2 backend, 6 weeks)
- Azure AD app registration flow per tenant
- OAuth2 + Microsoft Graph `CallRecords.Read.All` permission
- Webhook subscription for `callRecord` resource (push model)
- Fallback: list + delta query (pull model)
- Map Teams Call Records → NormalizedCdr
- Handle Auto Attendant + Call Queue analytics endpoints
- See `research/integrations/microsoft-teams.md`

### W14 — Webex Calling adapter (1 backend, 3 weeks)
- OAuth2 with `spark-admin:calling_cdr_read` scope
- CDR Stream endpoint (continuous consume)
- CDR Feed fallback for backfill
- Webhook subscription (Detailed Call Records webhook in Partner Hub)
- See `research/integrations/webex-calling.md`

### W15 — Zoom Phone adapter (1 backend, 3 weeks)
- Zoom Marketplace app per tenant
- REST API for call logs (paginated)
- Webhook for real-time events (call completed, recording ready)
- Map Zoom Phone CDR → NormalizedCdr
- Multi-leg call reconstruction via `call_uuid`
- See `research/integrations/zoom-phone.md`

### W16 — Generic SIP / Asterisk / FreePBX / Yeastar / Grandstream (1 backend, 4 weeks)
- AGI / AMI listener for Asterisk-family
- CSV import for batch CDR
- HTTP webhook spec for "bring your own PBX"
- Pre-built configs for Yeastar, Grandstream, FreePBX

### W17 — LCR engine (1 backend + 0.5 frontend, 4 weeks)
- `Carrier` + `CarrierRateCard` models
- Rate-card CSV import (NDA format common in carriers)
- LCR query: given destination + carriers, return cheapest route
- Routing recommendations dashboard
- Margin analysis (carrier cost vs. customer rate)
- Per-customer carrier preferences

### W18 — Prepaid wallet + hybrid billing (1 backend + 0.5 frontend, 4 weeks)
- `Wallet` model per tenant
- Top-up via payment gateway → wallet credit
- Real-time balance deduction on call cost
- Hybrid: postpaid up to limit, then prepaid wallet, then suspend
- Auto top-up rules

### W19 — Reseller / white-label tier (2 backend + 1 frontend, 6 weeks)
- `Reseller` model (organization that resells to multiple `Company` records)
- Reseller-scoped admin (sees only own customers)
- Custom domain per reseller (CNAME + TLS via Let's Encrypt automation)
- Custom branding: logo, colors, email templates, PDF invoice template
- Reseller commission / rev-share automation
- Reseller MDF & deal-reg portal
- Per-reseller pricing override

### W20 — Drag-drop wallboard widgets (1 frontend, 4 weeks)
- Widget library (KPI tile, gauge, chart, table, ticker, agent grid)
- Save/load layouts per user / per company
- Multi-screen layouts
- Public-share (read-only URL) for wallboards
- Mobile-optimized layout

### W21 — KPI library + saved templates + SLA tracking (0.5 backend + 0.5 frontend, 3 weeks)
- Predefined KPIs: AHT, ASA, abandon rate, FCR, occupancy, queue length, etc.
- Saved report templates per industry vertical
- SLA definition (target % answered in N seconds)
- Real-time SLA gauge + breach alerts

### W22 — Tenant feature-flag system (0.5 backend, 2 weeks)
- Integrate Unleash or GrowthBook
- Per-tenant flag overrides
- Phased rollouts of new features

---

## Phase 2 timeline (12 weeks)

| Week | Workstreams in flight |
|---|---|
| 1-2 | W11 framework + W19 reseller architecture start |
| 3-4 | W12 Cisco CUCM + W13 Teams (start) + W19 continues |
| 5-6 | W13 Teams continues + W14 Webex + W17 LCR start |
| 7-8 | W14 Webex ship + W15 Zoom start + W18 wallet + W17 LCR continues |
| 9-10 | W15 Zoom ship + W16 generic SIP + W19 reseller portal ship |
| 11-12 | W20 wallboard widgets + W21 KPI/SLA + W22 flags + bug bash + partner onboarding |

---

## Engineering allocation

| Role | HC | Allocation |
|---|---|---|
| Backend A | 1 | W11, W12, W14, W15 |
| Backend B | 1 | W13, W17, W18 |
| Backend C | 1 | W16, W19, W22 |
| Frontend | 1 | W17 (UI), W19 (reseller portal), W20 (drag-drop), W21 (UI) |
| Partner Eng | 0.5 | onboarding adapters per customer, MDF/deal-reg system |

→ ~5 FTE for 12 weeks

---

## Acceptance criteria

| Criterion | Target |
|---|---|
| Live customer on each: 3CX, CUCM, Teams, Webex, Zoom, generic SIP | 1+ each |
| White-label MSP partners signed | 3+ |
| Reseller customer portal branded for each MSP | 3+ |
| LCR engine saving customer money (case study) | ≥15% savings on at least 1 customer |
| Wallboard customization adopted | ≥50% of customers customize at least 1 widget |
| Adapter SDK published for partners | ✅ |

---

## Risks

| Risk | Mitigation |
|---|---|
| Teams Graph API permission approval delays (admin consent) | Pre-build customer onboarding wizard; clear doc for IT admins |
| CUCM customer doesn't have permission to enable billing server | Document workaround: manual SFTP of CDR files |
| Webex CDR endpoint changes / quota limits | Use both Stream + Feed for redundancy |
| Reseller multi-tenancy complexity (auth, billing) | Strict architecture review; separate reseller-admin role early |
| LCR rate-card import is messy (every carrier different) | Build flexible CSV mapper UI; let customers map columns |
| White-label custom-domain TLS automation | Use AWS ACM + Route53 OR Let's Encrypt + cert-manager |
