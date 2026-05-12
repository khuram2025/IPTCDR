# Feature Catalog

Every feature considered, with: description, why it matters, complexity, and product line.

Legend:
- **Complexity:** XS (1-3 days), S (1 week), M (2-4 weeks), L (1-3 months), XL (3+ months)
- **Product line:** B = IPT Bill, I = IPT Insight, C = IPT Contact, P = Platform/foundational
- **Phase:** P1 (M0-3) / P2 (M3-6) / P3 (M6-12) / P4 (M12-18)

---

## Foundation & hygiene

| ID | Feature | Why | Cmplx | Line | Phase |
|---|---|---|---|---|---|
| F-001 | `.gitignore` for venv/pycache/log/staticfiles | Stop bloating repo | XS | P | P1 |
| F-002 | Vendor-neutral CallRecord schema (`source_pbx` field) | Unblocks all PBX adapters | M | P | P1 |
| F-003 | Multi-currency per company (SAR/AED/USD/EUR/EGP/QAR) | Non-KSA sales | S | P | P1 |
| F-004 | Multi-language UI (Arabic RTL + English) | MENA expansion | M | P | P1 |
| F-005 | Public REST API (DRF + OpenAPI/Swagger) | Integration & partner story | M | P | P1 |
| F-006 | API keys + rate limiting per key | API security | S | P | P1 |
| F-007 | Webhooks (outbound event subscriptions) | Real-time integrations | S | P | P1 |
| F-008 | Audit log per user + per company | Compliance | S | P | P1 |
| F-009 | 2FA at login (TOTP) | Security baseline | XS | P | P1 |
| F-010 | Structured logging (JSON, log levels) | Observability | XS | P | P1 |
| F-011 | CI/CD pipeline (GitHub Actions: tests + deploy) | Quality | S | P | P1 |
| F-012 | Staging environment | Safe deploys | S | P | P1 |
| F-013 | Automated test suite (unit + integration) | Quality | M | P | P1 |
| F-014 | Tenant feature-flag system | Phased rollouts | S | P | P2 |
| F-015 | SSO (SAML 2.0 + OIDC: Azure AD, Google) | Enterprise | M | P | P3 |
| F-016 | Role-based API permissions | Security | S | P | P1 |

## Billing core (IPT Bill)

| ID | Feature | Why | Cmplx | Line | Phase |
|---|---|---|---|---|---|
| B-001 | Tax engine (VAT 15% configurable per company/country) | Required for invoices | S | B | P1 |
| B-002 | PDF invoice generator (with logo, branding, MENA address format) | Real billing SaaS | M | B | P1 |
| B-003 | Stripe payment gateway | Global card payments | S | B | P1 |
| B-004 | HyperPay / PayTabs / Tap (KSA + UAE) | Local payment | M | B | P1 |
| B-005 | Mada (KSA debit) | Local payment | M | B | P1 |
| B-006 | Recurring billing automation (monthly/annual) | SaaS basics | M | B | P1 |
| B-007 | Dunning workflows (retries, failed-payment emails) | Reduce churn | S | B | P1 |
| B-008 | Customer self-serve portal (view/pay/download invoices) | Reduce support load | M | B | P1 |
| B-009 | Prepaid wallet model | Match competitors | M | B | P2 |
| B-010 | Postpaid model (current default) | Already partial | S | B | P1 |
| B-011 | Hybrid prepaid+postpaid with overdraft | Enterprise flexibility | M | B | P2 |
| B-012 | LCR (Least-Cost Routing) engine | Carrier savings | L | B | P2 |
| B-013 | Multi-carrier rate-card import (CSV, NDA-format) | LCR foundation | S | B | P2 |
| B-014 | Margin / markup configuration per customer | Reseller model | S | B | P2 |
| B-015 | Reseller / wholesale tier (whitelabel multi-customer admin) | Channel revenue | L | B | P2 |
| B-016 | Branded customer portal per reseller | White-label | M | B | P2 |
| B-017 | Reseller commissions / rev-share automation | Channel ops | M | B | P2 |
| B-018 | Promo codes / discounts / coupons | Sales tools | S | B | P2 |
| B-019 | Credit notes / refunds workflow | Financial ops | S | B | P2 |
| B-020 | Quote-to-cash workflow (CPQ) | Enterprise sales | M | B | P3 |
| B-021 | DID inventory management (port-in/out, vanity) | Carrier-class | L | B | P4 |
| B-022 | Carrier integration (SBC visibility) | Wholesale | L | B | P4 |
| B-023 | Number portability workflow | Carrier ops | L | B | P4 |
| B-024 | Multi-entity billing (parent/child orgs) | Enterprise | M | B | P3 |

## PBX adapters (P2 multi-PBX)

| ID | Feature | Why | Cmplx | Line | Phase |
|---|---|---|---|---|---|
| A-001 | Cisco CUCM CDR adapter (FTP/SFTP pull) | #1 enterprise PBX | M | P | P2 |
| A-002 | Cisco CUBE CDR adapter | Cisco SBC | M | P | P2 |
| A-003 | Microsoft Teams Graph API adapter | Fastest growing | L | P | P2 |
| A-004 | Webex Calling Detailed Call History API | Cisco cloud | M | P | P2 |
| A-005 | Webex Calling CDR Stream / webhook | Real-time | S | P | P2 |
| A-006 | Zoom Phone API + webhook adapter | SMB explosion | M | P | P2 |
| A-007 | Generic SIP / Asterisk / FreePBX adapter | Long tail | M | P | P2 |
| A-008 | Yeastar adapter | APAC / SMB | S | P | P2 |
| A-009 | Grandstream adapter | SMB / hospitality | S | P | P2 |
| A-010 | Avaya CDR adapter | Legacy enterprise | M | P | P3 |
| A-011 | Mitel CDR adapter | Mid-market | M | P | P3 |
| A-012 | RingCentral / Vonage / 8x8 adapters | UCaaS players | M | P | P3 |
| A-013 | NEC SV9100 adapter | APAC enterprise | M | P | P4 |
| A-014 | Dialer integration (Convoso, ICTBroadcast, Vicidial) | Outbound | M | P | P3 |

## Reporting & analytics (IPT Insight)

| ID | Feature | Why | Cmplx | Line | Phase |
|---|---|---|---|---|---|
| I-001 | Real-time wallboard via WebSocket (Django Channels) | Demo killer | M | I | P1 |
| I-002 | Customizable wallboard widgets (drag-drop) | Variphy-class | L | I | P2 |
| I-003 | Multi-screen wallboard projection mode | Call-center floors | S | I | P2 |
| I-004 | Custom report builder (drag-drop, save, share) | Replaces dev requests | L | I | P3 |
| I-005 | Scheduled report email delivery (daily/weekly/monthly) | Automation | S | I | P1 |
| I-006 | Power BI / Tableau / Looker connectors | BI integration | M | I | P3 |
| I-007 | Saved filter sets / report templates | Productivity | S | I | P2 |
| I-008 | KPI library (predefined call-center KPIs) | Best practice | S | I | P2 |
| I-009 | Trend analysis & anomaly detection | AI insights | M | I | P3 |
| I-010 | Cross-tenant benchmarking (anonymized) | Market intelligence | M | I | P4 |
| I-011 | SLA tracking & breach alerts | Contact center | S | I | P2 |
| I-012 | Heatmaps (call volume by hour/day) | Visual insight | S | I | P1 |
| I-013 | Geo-map of call origin/destination | Visual insight | S | I | P2 |
| I-014 | Sankey diagram of IVR flows | Journey analytics | M | I | P3 |
| I-015 | Cost-per-customer-acquisition reports | Sales/marketing tie-in | M | I | P3 |
| I-016 | Agent leaderboards & gamification | Engagement | S | I | P3 |
| I-017 | Mobile-optimized dashboards | Remote supervisors | M | I | P2 |
| I-018 | Mobile app (iOS/Android, native or PWA) | 2026 expectation | L | I | P3 |
| I-019 | Real-time alerts via SMS/email/push/Slack/Teams | Active monitoring | S | I | P1 |
| I-020 | Threshold-based alert rules engine | Customizable monitoring | M | I | P2 |

## Call recording & QA (IPT Contact)

| ID | Feature | Why | Cmplx | Line | Phase |
|---|---|---|---|---|---|
| C-001 | Call recording (S3-compatible storage, encrypted) | Foundation | M | C | P3 |
| C-002 | Recording modes: Always-On / On-Demand / Selective | Imagicle parity | S | C | P3 |
| C-003 | Recording playback UI with waveform + transcript | Modern UX | M | C | P3 |
| C-004 | Retention policies (per company, per recording) | Compliance | S | C | P3 |
| C-005 | Encryption at rest (AES-256) + key rotation | Compliance | M | C | P3 |
| C-006 | Auto-pause on DTMF / payment screen detection | PCI compliance | M | C | P3 |
| C-007 | Manual pause/resume by agent | PCI compliance | XS | C | P3 |
| C-008 | Recording search (by caller, agent, date, keyword) | Usability | M | C | P3 |
| C-009 | Recording sharing (signed URLs, role-restricted) | Collaboration | S | C | P3 |
| C-010 | Recording deletion workflows (GDPR right-to-erasure) | Compliance | S | C | P3 |
| C-011 | Auto-transcription (Whisper / Azure / Google STT) | AI foundation | M | C | P3 |
| C-012 | Arabic transcription (MSA + Gulf dialect) | MENA differentiator | M | C | P3 |
| C-013 | Speaker diarization (who said what) | Modern STT | S | C | P3 |
| C-014 | Sentiment analysis per call | AI insight | M | C | P3 |
| C-015 | Emotion detection (happy/frustrated/angry) | Advanced AI | M | C | P3 |
| C-016 | Topic & keyword spotting + alerts | Business intel | M | C | P3 |
| C-017 | Auto-summary per call (LLM-generated) | Save agent time | S | C | P3 |
| C-018 | Auto QA scorecards (configurable rubric) | Replaces manual QA | L | C | P3 |
| C-019 | QA scorecard builder (drag-drop) | Customer ops | M | C | P3 |
| C-020 | Coaching workflows (assign clips, comment, approve) | Agent dev | M | C | P3 |
| C-021 | Compliance flagging (script adherence, mandatory disclosures) | Banking/insurance | M | C | P3 |
| C-022 | PCI redaction (auto-mute card / CVV) | Regulated industries | M | C | P3 |
| C-023 | PII redaction (names, ID numbers) | GDPR | M | C | P3 |
| C-024 | Translation (Arabic ↔ English call summaries) | Cross-language teams | S | C | P3 |
| C-025 | Voice-of-customer dashboards | Exec insights | M | C | P3 |
| C-026 | Topics-of-the-week / trends report | Product insights | S | C | P3 |
| C-027 | SAMA-compliant 10-year retention bundle | KSA banking | M | C | P3 |

## Workforce management (IPT Contact)

| ID | Feature | Why | Cmplx | Line | Phase |
|---|---|---|---|---|---|
| W-001 | Forecasting (ML on call history) | WFM foundation | L | C | P3 |
| W-002 | Shift scheduling | Match supply to demand | L | C | P3 |
| W-003 | Adherence tracking (real-time) | Supervisor tool | M | C | P3 |
| W-004 | Leave/PTO request & approval | HR integration | S | C | P3 |
| W-005 | Skill-based routing config | Routing engine | M | C | P3 |
| W-006 | Intraday adjustment (re-forecast mid-shift) | Operations | M | C | P3 |
| W-007 | Schedule swap (agent-to-agent) | Engagement | S | C | P3 |
| W-008 | Calendar sync (Google / Outlook) | Convenience | S | C | P4 |
| W-009 | What-if scenario planning | Capacity planning | M | C | P4 |
| W-010 | Multi-channel forecasting (voice + chat + email) | Omnichannel WFM | M | C | P4 |

## Omnichannel (IPT Contact)

| ID | Feature | Why | Cmplx | Line | Phase |
|---|---|---|---|---|---|
| O-001 | WhatsApp Business API integration | MENA growth | M | C | P3 |
| O-002 | Web chat widget | Common request | M | C | P3 |
| O-003 | Email channel ingestion (IMAP/SMTP) | Help-desk replacement | M | C | P3 |
| O-004 | SMS inbound/outbound | Notifications + 2-way | S | C | P3 |
| O-005 | Facebook Messenger integration | Social CX | M | C | P4 |
| O-006 | Instagram DM integration | Social CX | M | C | P4 |
| O-007 | Unified agent inbox (omnichannel queue) | Modern UX | L | C | P3 |
| O-008 | Channel routing rules engine | Routing | M | C | P3 |
| O-009 | Bot handoff (chatbot → human) | Automation | M | C | P4 |
| O-010 | Customer profile / contact card | 360° view | M | C | P3 |

## Fraud & security

| ID | Feature | Why | Cmplx | Line | Phase |
|---|---|---|---|---|---|
| S-001 | Toll-fraud rule engine (intl spike, after-hours, blacklist) | Quick win revenue | M | B | P1 |
| S-002 | ML-based anomaly detection on call patterns | Advanced fraud | L | B | P3 |
| S-003 | Country block-list / allow-list per company | Prevention | XS | B | P1 |
| S-004 | Premium-rate destination warnings | Prevention | XS | B | P1 |
| S-005 | Velocity rules (calls/min, duration, cost) | Prevention | S | B | P1 |
| S-006 | Real-time SMS/email/Slack alerts on fraud | Active defense | XS | B | P1 |
| S-007 | Auto-disable extension on fraud detection | Containment | XS | B | P1 |
| S-008 | Fraud incident dashboard + timeline | Investigation | S | B | P1 |
| S-009 | Free toll-fraud audit report (lead magnet) | GTM tool | S | B | P1 |
| S-010 | DLP (data loss prevention) for recordings | Enterprise | M | C | P4 |
| S-011 | IP whitelisting per company portal | Security | XS | P | P1 |
| S-012 | Encryption-at-rest for all PII | Compliance | M | P | P3 |

## Call quality & monitoring

| ID | Feature | Why | Cmplx | Line | Phase |
|---|---|---|---|---|---|
| Q-001 | MOS / jitter / packet-loss capture from CDR | Quality dashboard | M | I | P3 |
| Q-002 | Call quality dashboard (per call, per route, per carrier) | Troubleshooting | M | I | P3 |
| Q-003 | Carrier comparison (which trunk gives best quality?) | Operations | S | I | P3 |
| Q-004 | Quality threshold alerts | Active monitoring | S | I | P3 |
| Q-005 | Codec usage analytics | Optimization | S | I | P3 |
| Q-006 | Real-time RTP monitoring (advanced) | Network ops | L | I | P4 |

## CRM & integrations

| ID | Feature | Why | Cmplx | Line | Phase |
|---|---|---|---|---|---|
| X-001 | Salesforce integration (call logging, click-to-call, screen pop) | Sales teams | M | I/C | P4 |
| X-002 | HubSpot integration | Sales teams | M | I/C | P4 |
| X-003 | Zoho CRM integration | Mid-market | S | I/C | P4 |
| X-004 | Bitrix24 integration | RU/CIS market | S | I/C | P4 |
| X-005 | Odoo integration | SMB ERP | S | I/C | P4 |
| X-006 | Microsoft Dynamics 365 integration | Enterprise | M | I/C | P4 |
| X-007 | Pipedrive integration | SMB sales | S | I/C | P4 |
| X-008 | Zendesk integration (ticket sync) | Help desk | M | C | P4 |
| X-009 | Freshdesk integration | Help desk | M | C | P4 |
| X-010 | Intercom integration | SaaS support | M | C | P4 |
| X-011 | Slack notifications & alerts | Team comms | S | I | P1 |
| X-012 | Microsoft Teams notifications | Team comms | S | I | P1 |
| X-013 | Zapier / Make.com integration | Long tail | M | P | P3 |
| X-014 | n8n self-hosted automation support | Open source fans | S | P | P3 |
| X-015 | Power BI connector | Enterprise BI | M | I | P3 |
| X-016 | Generic SQL / data warehouse export (BigQuery, Snowflake, Redshift) | Data teams | M | I | P4 |
| X-017 | Public iCal feed (calendar-based reports) | Niche | XS | I | P3 |

## AI voice agent (P4)

| ID | Feature | Why | Cmplx | Line | Phase |
|---|---|---|---|---|---|
| V-001 | Inbound IVR replacement (intent-based) | Cost reduction | L | C | P4 |
| V-002 | Outbound campaign bot (surveys, confirmations) | Productivity | L | C | P4 |
| V-003 | FAQ deflection bot | Volume reduction | M | C | P4 |
| V-004 | Appointment booking bot | Healthcare/services | L | C | P4 |
| V-005 | Voice-to-CRM (auto-create records) | Sales | M | C | P4 |
| V-006 | Bot supervisor handoff | Operations | M | C | P4 |
| V-007 | Multi-language bot (Arabic + English + Urdu + Hindi + Tagalog) | MENA workforce | M | C | P4 |
| V-008 | Custom voice cloning (brand voice) | Premium | M | C | P4 |

## Outbound dialer

| ID | Feature | Why | Cmplx | Line | Phase |
|---|---|---|---|---|---|
| D-001 | Predictive dialer | BPO market | L | C | P4 |
| D-002 | Power dialer | SMB sales | M | C | P4 |
| D-003 | Preview dialer | High-touch sales | S | C | P4 |
| D-004 | Answering machine detection (AMD) | Efficiency | M | C | P4 |
| D-005 | Voicemail drop | Productivity | S | C | P4 |
| D-006 | DNC (Do Not Call) list management | Compliance | S | C | P4 |
| D-007 | Time-zone aware dialing | Compliance | S | C | P4 |
| D-008 | Abandonment rate enforcement (<3% per TCPA) | Compliance | S | C | P4 |
| D-009 | Campaign management dashboard | Operations | M | C | P4 |
| D-010 | Lead list management & dispositioning | Sales ops | M | C | P4 |

## Compliance & certifications

| ID | Feature | Why | Cmplx | Line | Phase |
|---|---|---|---|---|---|
| Z-001 | GDPR data export per user | Compliance | S | P | P3 |
| Z-002 | GDPR right-to-erasure workflow | Compliance | S | P | P3 |
| Z-003 | Consent logging (recording opt-in/out) | Compliance | S | P | P3 |
| Z-004 | Data residency selector (KSA, UAE, EU) | Enterprise + govt | L | P | P4 |
| Z-005 | SOC 2 Type II readiness program | Enterprise gate | XL | P | P4 |
| Z-006 | ISO 27001 readiness program | Enterprise gate | XL | P | P4 |
| Z-007 | PCI DSS attestation | Banks/payments | L | P | P4 |
| Z-008 | SAMA compliance documentation pack | KSA banking | M | P | P3 |
| Z-009 | CITC compliance documentation pack | KSA general | M | P | P3 |
| Z-010 | Pen-test program (annual) | Trust | M | P | P3 |
| Z-011 | Vendor risk questionnaire library | Sales enablement | S | P | P3 |
| Z-012 | Trust center page (public) | Marketing | S | P | P3 |

---

## Counts

- **Total features cataloged:** ~180
- **Phase 1 (M0-3):** ~35 features
- **Phase 2 (M3-6):** ~25 features
- **Phase 3 (M6-12):** ~70 features
- **Phase 4 (M12-18):** ~50 features

→ Sequencing logic + scoring in `02-gap-analysis.md`
→ Granular tickets per phase in `tasks/`
