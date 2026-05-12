# 18-Month Roadmap

Sequenced plan to evolve from "3CX-only billing" → "MENA-leading multi-PBX UC analytics, billing, and AI CX platform."

---

## Phase 1 — Foundations & Quick Wins (Months 0-3)

**Theme:** "Plug the worst gaps. Look enterprise-ready. Generate first new revenue."

### Outcomes
- Multi-currency, multi-language (Arabic RTL) UI
- Real billing SaaS (invoicing + payments + tax engine)
- Real-time wallboard
- Toll-fraud alerting (new revenue line, lead magnet)
- Public REST API + webhooks
- Customer self-serve portal
- Code-base hygiene + CI/CD + staging

### Headline features
1. `.gitignore` cleanup + git history audit (F-001)
2. Vendor-neutral CallRecord schema (F-002)
3. Multi-currency (F-003) + Tax engine (B-001)
4. Arabic RTL UI (F-004)
5. PDF invoice generator (B-002) + HyperPay/PayTabs/Stripe payment gateways (B-003, B-004)
6. Recurring billing automation + dunning (B-006, B-007)
7. Customer self-serve portal (B-008)
8. Public REST API (DRF + OpenAPI) (F-005, F-006, F-007)
9. Real-time wallboard via Django Channels (I-001)
10. Toll-fraud rule engine + free-audit lead magnet (S-001 → S-009)
11. 2FA login + audit log + structured logging (F-008, F-009, F-010)
12. CI/CD + staging + automated tests (F-011, F-012, F-013)
13. Slack / Teams / SMS / email alerts (X-011, X-012, I-019)
14. Scheduled report email delivery (I-005)
15. Heatmaps + visual upgrades (I-012)

### KPIs
- ✅ 100% of new code covered by CI tests
- ✅ Zero `.pyc` / `venv/` / `*.log` files in repo
- ✅ ≥3 paying customers on new fraud add-on
- ✅ ≥1 customer outside KSA (to validate multi-currency)
- ✅ Wallboard live in 5+ customer offices
- ✅ Public API has ≥1 partner / ISV consuming it

### Engineering load
- 2 backend engineers (Django, Channels, payment gateways)
- 1 frontend engineer (Arabic RTL, wallboard UI, customer portal)
- 0.5 DevOps (staging, CI/CD)

---

## Phase 2 — Multi-PBX & White-Label (Months 3-6)

**Theme:** "Stop being '3CX only.' Become 'any UC platform.' Open the partner channel."

### Outcomes
- Cisco CUCM / MS Teams / Webex Calling / Zoom Phone / generic SIP adapters
- Reseller / white-label tier with branded customer portals
- LCR engine
- Prepaid + postpaid + hybrid billing models
- Customizable wallboard widgets

### Headline features
1. Cisco CUCM CDR adapter via FTP/SFTP (A-001) — see `research/integrations/cisco-cucm.md`
2. Microsoft Teams Graph API adapter (A-003) — see `research/integrations/microsoft-teams.md`
3. Webex Calling CDR adapter (A-004, A-005) — see `research/integrations/webex-calling.md`
4. Zoom Phone API + webhook adapter (A-006) — see `research/integrations/zoom-phone.md`
5. Generic SIP / Asterisk / FreePBX / Yeastar / Grandstream adapters (A-007 → A-009)
6. PBX adapter framework (pluggable, contributor-friendly)
7. LCR engine + multi-carrier rate-card import (B-012, B-013)
8. Prepaid wallet + hybrid billing (B-009, B-011)
9. Reseller / white-label tier (B-014 → B-017)
10. Drag-drop wallboard widgets (I-002), multi-screen projection (I-003)
11. KPI library + saved templates (I-007, I-008)
12. SLA tracking & breach alerts (I-011)
13. Tenant feature-flag system (F-014)
14. Mobile-optimized dashboards (I-017)
15. Heatmaps geo + threshold alerts engine (I-013, I-020)

### KPIs
- ✅ Live customers on at least 3 different PBX platforms (3CX + Cisco + Teams or Zoom)
- ✅ ≥3 white-label MSP partners signed
- ✅ ≥10 LCR routes configured by customers
- ✅ Wallboard customization used by 50%+ of customers

### Engineering load
- 2-3 backend engineers (PBX adapters)
- 1 frontend engineer (drag-drop widgets, reseller portal)
- 0.5 partner/CS engineer (onboarding adapters per customer)

---

## Phase 3 — AI & Contact-Center Suite (Months 6-12)

**Theme:** "Enter the $3.2B AI/CX market. Become a real contact-center platform."

### Outcomes
- Call recording with PCI/SAMA-compliant retention
- Arabic + English transcription, sentiment, summary, topic spotting
- Auto QA scorecards with coaching workflows
- WFM-lite (forecasting, scheduling, adherence)
- Omnichannel ingestion (WhatsApp, web chat, email, SMS)
- Mobile app (iOS / Android / PWA)
- SSO (Azure AD, Google)
- Call quality monitoring (MOS / jitter / packet-loss)
- Compliance documentation pack (SAMA, CITC, GDPR)

### Headline features
1. Call recording infrastructure (S3-compatible, encrypted) (C-001 → C-010)
2. Whisper / Azure / Google STT integration (C-011) + Arabic STT (C-012) + diarization (C-013)
3. Sentiment + emotion + topic spotting (C-014 → C-016)
4. Auto QA scorecards + builder + coaching workflows (C-018 → C-020)
5. PCI / PII redaction (C-022, C-023)
6. SAMA-compliant 10-year retention bundle (C-027)
7. Custom report builder + Power BI / Tableau / Looker (I-004, I-006)
8. Trend / anomaly detection (I-009)
9. Sankey IVR flows + journey analytics (I-014)
10. Agent leaderboards & gamification (I-016)
11. Mobile app (I-018) + push notifications
12. WFM-lite: forecasting + scheduling + adherence (W-001 → W-006)
13. Omnichannel: WhatsApp + chat + email + SMS + unified inbox (O-001 → O-008)
14. Customer profile / 360° view (O-010)
15. SSO (F-015) + GDPR workflows (Z-001 → Z-003)
16. Call quality monitoring (Q-001 → Q-005)
17. Compliance docs pack: SAMA + CITC (Z-008, Z-009) + trust center (Z-012)
18. Pen-test program (Z-010)
19. Zapier / n8n / Power BI connectors (X-013 → X-015)

### KPIs
- ✅ ≥5,000 hours of audio transcribed/month
- ✅ ≥3 banking or insurance customers using SAMA bundle
- ✅ ≥10 customers using WFM module
- ✅ Mobile app in App Store + Play Store with 4+ rating
- ✅ ≥3 omnichannel customers (mixing voice + WhatsApp)
- ✅ Pen-test report clean

### Engineering load
- 3-4 backend (recording, transcription pipeline, QA, WFM)
- 2 frontend (custom report builder, mobile app, omnichannel UI)
- 1 ML engineer (sentiment, anomaly, custom Arabic STT tuning)
- 1 security/compliance engineer

---

## Phase 4 — Platform & Adjacent Revenue (Months 12-18)

**Theme:** "Become the platform, not a tool. Expand into AI voice agents, dialers, CRM-deep integrations, govt/banking verticals."

### Outcomes
- CRM integrations (Salesforce, HubSpot, Zoho, Bitrix24, Odoo, Dynamics, Pipedrive)
- Help-desk integrations (Zendesk, Freshdesk, Intercom)
- AI voice agent product (inbound IVR replacement, outbound campaigns)
- Predictive / power dialer (BPO market)
- DID / number inventory + carrier integration
- SOC 2 Type II + ISO 27001 + PCI DSS
- Multi-region data residency (KSA, UAE, EU)
- Cross-tenant benchmarking
- Vertical bundles (Bank, Health, Hospitality, Government)

### Headline features
1. Salesforce / HubSpot / Zoho / Bitrix24 / Odoo / Dynamics / Pipedrive (X-001 → X-007)
2. Zendesk / Freshdesk / Intercom (X-008 → X-010)
3. AI voice agent: inbound IVR + outbound campaigns + FAQ + booking (V-001 → V-008)
4. Predictive / power / preview dialer + AMD + voicemail drop + DNC (D-001 → D-010)
5. DID inventory + number portability + carrier integration (B-021 → B-023)
6. SBC visibility (B-022)
7. Multi-entity billing (B-024)
8. Quote-to-cash CPQ (B-020)
9. Cross-tenant benchmarking (anonymized) (I-010)
10. Real-time RTP monitoring (Q-006)
11. Data residency selector (Z-004)
12. SOC 2 Type II + ISO 27001 + PCI DSS (Z-005 → Z-007)
13. Multi-channel WFM forecasting + what-if scenarios + intraday (W-009, W-010)
14. Calendar sync (W-008) + schedule swap (W-007)
15. Generic SQL / data-warehouse export (X-016)
16. Avaya / Mitel / RingCentral / Vonage / 8x8 / NEC adapters (A-010 → A-013)
17. Custom voice cloning (V-008)
18. ML-based fraud anomaly detection (S-002)
19. DLP for recordings (S-010)
20. Vertical bundles (Bank, Health, Hospitality, Govt) — pre-configured templates

### KPIs
- ✅ ≥5 enterprise customers using SOC 2 attestation in procurement
- ✅ ≥1M minutes/month on AI voice agent product
- ✅ ≥10 customers running predictive dialer campaigns
- ✅ ≥3 banks live on SAMA-bundle + KSA data residency
- ✅ ≥SAR 10M ARR

### Engineering load
- 3 backend (CRM integrations, dialer, DID)
- 2 frontend (CRM widgets, dialer UI)
- 2 ML/AI (voice agent, conversation intelligence improvements)
- 1 compliance (SOC 2, ISO, PCI)
- 1 partner engineer (vertical templates)

---

## Cumulative engineering hires (planning estimate)

| Role | M0 | M3 | M6 | M12 | M18 |
|---|---|---|---|---|---|
| Backend | 2 | 3 | 4 | 5 | 5 |
| Frontend | 1 | 1 | 2 | 3 | 3 |
| Mobile | 0 | 0 | 0 | 1 | 1 |
| ML/AI | 0 | 0 | 1 | 2 | 2 |
| DevOps / SRE | 0.5 | 1 | 1 | 1 | 2 |
| Security / Compliance | 0 | 0 | 0 | 1 | 1 |
| **Total eng** | **3.5** | **5** | **8** | **13** | **14** |
| Sales / CS | 1 | 2 | 4 | 6 | 8 |

---

## Cross-cutting workstreams (every phase)

| Workstream | What |
|---|---|
| **Customer success** | Onboarding playbooks, KB articles, in-app product tours |
| **Marketing** | Landing pages per persona, content (blog, webinars, case studies in Arabic + English), 3CX/Teams/Cisco marketplace listings |
| **Partner program** | Reseller portal, deal-reg, MDF, certifications |
| **Compliance program** | Annual pen-test, SOC 2 audit prep, GDPR/SAMA/CITC documentation upkeep |
| **Performance & cost** | DB indexing, query optimization, AI cost monitoring, infra cost per tenant |

---

## Decision points / phase gates

Before moving to next phase, validate:

- **Phase 1 → 2:** ≥3 paying customers on new SaaS pricing; payment gateway proven; wallboard demoed in ≥10 sales calls; first non-KSA customer
- **Phase 2 → 3:** ≥1 live customer on each of CUCM, Teams, Zoom; ≥3 white-label MSPs onboarded; LCR saving ≥1 customer ≥15% on calls
- **Phase 3 → 4:** ≥3 banks/insurers using recording bundle; ≥10 customers using transcription/QA; mobile app shipped; SOC 2 Type I report obtained
- **Phase 4 exit (M18):** ≥SAR 10M ARR; ≥5 enterprise wins via SOC 2; AI voice agent product generating ≥SAR 500k ARR

→ Per-phase task lists in `tasks/phase{1,2,3,4}-tasks.md`
