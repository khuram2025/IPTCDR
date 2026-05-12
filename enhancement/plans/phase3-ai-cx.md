# Phase 3 — AI & Contact-Center Suite (Months 6-12)

**Theme:** Enter the $3.2B AI/CX market. Become a real contact-center platform.

---

## Goals

1. Call recording (S3-compatible, encrypted, SAMA-grade retention)
2. Arabic + English transcription, speaker diarization, sentiment, topic spotting, summaries
3. Auto QA scorecards + coaching workflows
4. WFM-lite (forecasting, scheduling, adherence)
5. Omnichannel ingestion (WhatsApp, web chat, email, SMS) + unified inbox
6. Mobile app (iOS / Android / PWA)
7. SSO (Azure AD, Google)
8. Call quality monitoring (MOS / jitter / packet-loss)
9. Compliance documentation pack (SAMA, CITC, GDPR)
10. Custom report builder + Power BI / Tableau / Looker connectors

## Workstreams

### W23 — Call recording infrastructure (2 backend, 6 weeks)
- Audio receiver service (RTP fork from PBX OR post-call upload)
- S3-compatible encrypted storage (per-tenant KMS key)
- `CallRecording` model with metadata, retention, access policy
- Recording modes: Always-On / On-Demand / Selective (rule-based)
- Retention policies (per company, per recording, automatic delete)
- AES-256 encryption + key rotation
- Per-tenant KSA region storage option

### W24 — Recording UI (1 frontend, 4 weeks)
- Playback with waveform + scrubber
- Side-by-side transcript with click-to-jump
- Search recordings (by caller, agent, date, keyword in transcript)
- Sharing via signed URLs (role-restricted, time-limited)
- Manual delete + GDPR right-to-erasure workflow
- Manual pause/resume controls (PCI compliance)

### W25 — Transcription pipeline (1 ML + 1 backend, 6 weeks)
- Whisper self-hosted (English, MSA Arabic)
- Azure Speech (Gulf/Saudi dialect Arabic)
- Speaker diarization (who said what)
- Worker queue with auto-scaling
- Per-tenant minute meter + cost tracking
- Failure retry + DLQ
- Result store: transcripts in OpenSearch (full-text) + ClickHouse (analytics)

### W26 — Sentiment + topic + summary AI (1 ML, 4 weeks)
- Sentiment per turn + per call (positive/negative/neutral score)
- Emotion detection (happy/frustrated/angry/calm)
- Topic spotting (configurable keywords + ML topic clusters)
- LLM-generated call summary (3-bullet TL;DR)
- Translation (Arabic ↔ English summaries)
- Voice-of-customer dashboards

### W27 — PCI / PII redaction (1 ML + 0.5 backend, 4 weeks)
- DTMF detection → auto-mute in audio
- Card number / CVV / IBAN regex in transcript → redact
- PII (Saudi National ID, Iqama) → redact
- Configurable per-tenant rules
- Audit trail of redactions

### W28 — Auto QA scorecards (1 backend + 1 frontend, 6 weeks)
- `QAScorecard` model: rubric of weighted criteria
- Drag-drop scorecard builder
- AI-evaluated criteria (e.g., "agent introduced themselves" via transcript NLP)
- Manual-evaluated criteria (yes/no toggles for QA reviewer)
- QA workflow: assign call → reviewer scores → discuss with agent → resolve
- Scorecard analytics dashboard

### W29 — Coaching workflows (0.5 frontend, 2 weeks)
- Clip and bookmark moments in calls
- Assign clip to agent with comment
- Agent acknowledgment / response
- Coaching session scheduling

### W30 — WFM-lite (2 backend + 1 frontend, 8 weeks)
- Forecasting: ML on call history (Prophet, ARIMA, or simpler regression first)
- Schedule generation: respect skills, shifts, breaks
- Adherence tracking (real-time deviation from schedule)
- Leave/PTO request + approval workflow
- Skill-based routing config UI
- Intraday adjustment (re-forecast mid-shift)
- Schedule swap (agent-to-agent)

### W31 — Omnichannel ingestion (2 backend + 1 frontend, 8 weeks)
- WhatsApp Business API (via Meta Cloud API or 360dialog/Twilio)
- Web chat widget (embeddable JS)
- Email channel (IMAP polling + SMTP send)
- SMS (inbound + outbound via Unifonic/Twilio)
- Channel routing rules engine
- Unified agent inbox (omnichannel queue)
- Customer profile / contact card (cross-channel history)

### W32 — Mobile app (2 mobile, 12 weeks)
- React Native (single codebase iOS + Android) OR Flutter
- Supervisor wallboard view
- Real-time alerts via push
- Approve/deny WFM requests on the go
- View recent calls + listen to recordings
- Fraud alert acknowledgment
- Quick actions: disable extension, top-up wallet, etc.

### W33 — SSO + GDPR (1 backend, 4 weeks)
- SAML 2.0 (Azure AD, Okta, OneLogin)
- OIDC (Google, Azure AD)
- Just-in-time user provisioning
- GDPR: data export per user, right-to-erasure workflow, consent logging

### W34 — Call quality monitoring (1 backend + 0.5 frontend, 4 weeks)
- Capture MOS / jitter / packet-loss from CDR (where available per PBX)
- Quality dashboard per call / per route / per carrier
- Carrier comparison view
- Threshold alerts
- Codec usage analytics

### W35 — Compliance pack (1 compliance + 0.5 backend, ongoing)
- SAMA documentation pack: 10-yr retention controls, audit certification, immutable storage
- CITC pack: international call routing, licensing
- PDPL (KSA Personal Data Protection Law) workflows
- Trust center page (public)
- Vendor risk questionnaire library
- Pen-test annual program (external vendor)

### W36 — Custom report builder + BI connectors (1 backend + 1 frontend, 6 weeks)
- Drag-drop report builder UI (fields, filters, group-bys, charts)
- Save / share / schedule
- Report subscriptions (email)
- Power BI connector (DirectQuery)
- Tableau connector (web data connector)
- Looker connector
- Generic SQL endpoint (read-only) for data warehouses

### W37 — Trend / anomaly detection + journey analytics (0.5 ML + 0.5 frontend, 4 weeks)
- Trend detection on call volumes, costs, sentiment
- Anomaly detection (sudden drop in answer rate, fraud-like patterns)
- Sankey IVR flow visualization
- Customer journey across channels

### W38 — Engagement tools (0.5 frontend, 2 weeks)
- Agent leaderboards
- Gamification: badges, points
- Team competitions
- Manager nominations / recognition

---

## Phase 3 timeline (24 weeks ≈ 6 months)

| Month | Highlight |
|---|---|
| M7 | W23 recording infra + W25 transcription start + W33 SSO |
| M8 | W23/W25 ship + W24 recording UI + W26 sentiment/AI start |
| M9 | W26 ship + W27 PCI/PII + W28 QA scorecards start + W30 WFM forecasting model |
| M10 | W28 QA ship + W29 coaching + W30 WFM scheduler + W31 omnichannel start (WhatsApp first) |
| M11 | W30 WFM ship + W31 omnichannel chat+email + W34 call quality + W36 report builder start |
| M12 | W31 omnichannel SMS + unified inbox + W32 mobile MVP + W36 report builder ship + W35 SAMA pack + W37/W38 |

---

## Engineering allocation

| Role | HC | Allocation |
|---|---|---|
| Backend A | 1 | W23 recording, W27 redaction, W31 omnichannel |
| Backend B | 1 | W25 transcription pipeline, W28 QA, W36 reports |
| Backend C | 1 | W30 WFM, W31 omnichannel, W34 quality |
| Backend D | 1 | W33 SSO, W35 compliance, W37 anomaly |
| Frontend A | 1 | W24 recording UI, W28 QA UI, W36 report builder |
| Frontend B | 1 | W30 WFM UI, W31 unified inbox, W37/W38 |
| ML/AI | 1-2 | W25, W26, W27 redaction NLP, W37 anomaly detection |
| Mobile | 2 | W32 React Native iOS + Android |
| Compliance | 1 | W35 ongoing |

→ ~10-12 FTE for 6 months

---

## Acceptance criteria

| Criterion | Target |
|---|---|
| Hours of audio transcribed/month | 5,000+ |
| Banking/insurance customers using SAMA bundle | 3+ |
| Customers using WFM module | 10+ |
| Mobile app rating | 4.0+ on stores |
| Omnichannel customers (voice + WhatsApp at minimum) | 3+ |
| Pen-test report | Clean / no high-severity findings |
| Custom report builder adoption | 30%+ of customers |
| SOC 2 Type I report obtained | ✅ |

---

## Risks

| Risk | Mitigation |
|---|---|
| Whisper Arabic accuracy below 85% WER | Use Azure Arabic for production, Whisper for cost-sensitive English |
| Audio storage costs scale faster than expected | Aggressive lifecycle: hot → IA at 30d → Glacier at 90d; offer customer to manage their own S3 bucket (BYOS) |
| Transcription costs squeeze margin | Charge per-minute add-on; cap free tier; meter aggressively |
| WhatsApp API rate limits | Use 360dialog or Twilio at scale; tier customers |
| WFM ML accuracy issues | Start with simple statistical baselines; add ML iteratively |
| Mobile app App Store / Play Store approval delays | Submit by week 8 of 12; Plan B is responsive web (PWA) |
| SSO integration complexity per customer | Build self-serve config; doc page per IDP |
| SAMA bundle audit findings | Engage SAMA-experienced compliance consultant; pre-audit dry run |
| Pen-test critical findings | Budget 2 weeks for remediation post-pen-test |
