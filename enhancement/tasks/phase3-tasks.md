# Phase 3 — Granular Task List (Months 6-12)

---

## EPIC: Call recording infrastructure

### P3-001 — Audio receiver service
- **AC:** Accepts RTP fork from PBX OR post-call HTTP upload; ~MOS detection on stream
- **Effort:** M

### P3-002 — S3-compatible encrypted storage
- **AC:** Per-tenant KMS key; encrypted at rest; multi-AZ; lifecycle policies
- **Effort:** S

### P3-003 — `CallRecording` model
- **AC:** Metadata, duration, file path, encryption key ref, retention until, access policy
- **Effort:** XS

### P3-004 — Recording modes (Always-On / On-Demand / Selective)
- **AC:** Configurable per company / extension / queue; Selective = rule-based (e.g., only record if duration > 30s and external)
- **Effort:** S

### P3-005 — Retention policies
- **AC:** Per-company default + per-recording override; auto-delete on expiry; tombstone audit log
- **Effort:** S

### P3-006 — KSA region storage option
- **AC:** Select region at company creation; recordings never leave region
- **Effort:** S

### P3-007 — Audit trail for access
- **AC:** Who listened to which recording when; immutable log
- **Effort:** S

---

## EPIC: Recording UI

### P3-008 — Playback page with waveform
- **AC:** wavesurfer.js or similar; click-to-seek; playback speed; download (if permitted)
- **Effort:** S

### P3-009 — Side-by-side transcript with click-to-jump
- **AC:** Transcript with timestamps; clicking jumps player; speaker labels
- **Effort:** S

### P3-010 — Recording search
- **AC:** Filter by caller, agent, date, queue, sentiment, keyword in transcript (OpenSearch full-text)
- **Effort:** M

### P3-011 — Sharing via signed URLs
- **AC:** Time-limited URL; role-restricted; audit-logged
- **Effort:** S

### P3-012 — Manual delete + GDPR right-to-erasure workflow
- **AC:** Customer requests → tracked ticket → after legal review → recordings deleted; export bundle if requested
- **Effort:** S

### P3-013 — Manual pause/resume controls (PCI)
- **AC:** Agent can pause recording during card capture; logged with reason
- **Effort:** XS

---

## EPIC: Transcription pipeline

### P3-014 — Whisper self-hosted (English + MSA Arabic)
- **AC:** GPU-backed inference service; queued; auto-scaling; cost capped
- **Effort:** M

### P3-015 — Azure Speech (Saudi/Gulf dialect Arabic)
- **AC:** Azure Speech-to-Text with Arabic dialect models; integrated as fallback / premium tier
- **Effort:** S

### P3-016 — Speaker diarization
- **AC:** pyannote.audio or similar; identifies agent vs. customer turns
- **Effort:** S

### P3-017 — Per-tenant minute meter
- **AC:** Track minutes used; enforce caps; alert on overage; bill to invoice
- **Effort:** S

### P3-018 — Transcription store (OpenSearch + ClickHouse)
- **AC:** Full-text in OpenSearch; aggregates in ClickHouse; metadata in Postgres
- **Effort:** S

### P3-019 — Failure retry + DLQ
- **AC:** 3 retries with backoff; DLQ for manual review; per-tenant alerts on chronic failures
- **Effort:** XS

---

## EPIC: Sentiment + topic + summary

### P3-020 — Sentiment per turn + per call
- **AC:** Score -1 to +1 per turn; aggregate per call; visualize on transcript
- **Effort:** S

### P3-021 — Emotion detection
- **AC:** Categorical: happy/calm/frustrated/angry; per turn
- **Effort:** S

### P3-022 — Topic spotting
- **AC:** Configurable keyword groups; ML-based clustering for unknown topics
- **Effort:** M

### P3-023 — LLM-generated summary (3-bullet TL;DR)
- **AC:** GPT-4 / Claude / local model; cached per recording
- **Effort:** S

### P3-024 — Translation (AR ↔ EN summaries)
- **AC:** On-demand translation of summaries
- **Effort:** S

### P3-025 — Voice-of-customer dashboards
- **AC:** Trending topics, sentiment over time, frequent complaints
- **Effort:** M

---

## EPIC: PCI / PII redaction

### P3-026 — DTMF detection + auto-mute
- **AC:** Detect DTMF tones in audio stream; mute audio + transcript during DTMF
- **Effort:** M

### P3-027 — Card / CVV / IBAN regex redaction
- **AC:** Post-transcription regex; replace with `[REDACTED]`; original deleted
- **Effort:** S

### P3-028 — Saudi National ID + Iqama redaction
- **AC:** Format-specific regex (10 digits starting 1xxx for citizen, 2xxx for Iqama)
- **Effort:** XS

### P3-029 — Configurable redaction rules per tenant
- **AC:** Tenant admin enables/disables specific rules; adds custom patterns
- **Effort:** S

### P3-030 — Redaction audit trail
- **AC:** What was redacted and when; for compliance review
- **Effort:** XS

---

## EPIC: Auto QA scorecards

### P3-031 — `QAScorecard` + `QACriterion` models
- **AC:** Scorecard has multiple criteria with weights; criterion is AI-evaluated or manual
- **Effort:** S

### P3-032 — Drag-drop scorecard builder UI
- **AC:** Add criteria; set weight; preview; save
- **Effort:** M

### P3-033 — AI evaluators
- **AC:** "Did agent introduce themselves?" → LLM checks transcript; "Did agent say required disclaimer?" → keyword/regex
- **Effort:** M

### P3-034 — Manual review workflow
- **AC:** Assign call to QA reviewer; reviewer scores manual criteria; submit; agent notified
- **Effort:** S

### P3-035 — Scorecard analytics
- **AC:** Per-agent scores over time; team/queue averages; drill into low-scoring criteria
- **Effort:** S

### P3-036 — Compliance flagging
- **AC:** "Mandatory disclosure missing" → ticket auto-created
- **Effort:** S

---

## EPIC: Coaching workflows

### P3-037 — Clip + bookmark in calls
- **AC:** Highlight transcript segment → save as clip → metadata
- **Effort:** S

### P3-038 — Assign clip to agent with comment
- **AC:** Agent receives notification; views clip; acknowledges
- **Effort:** XS

### P3-039 — Coaching session scheduling
- **AC:** Manager schedules 1:1; calendar integration; agenda notes
- **Effort:** S

---

## EPIC: WFM-lite

### P3-040 — Forecasting model (statistical baseline)
- **AC:** Time-series model (ARIMA / Prophet) on historical call volumes; ±10% MAPE on hourly forecast
- **Effort:** M

### P3-041 — Schedule generator
- **AC:** Match forecast to required agents; respect skills, shifts, max-hours, breaks
- **Effort:** L

### P3-042 — Adherence tracking
- **AC:** Real-time: agent status vs. scheduled state; deviation %
- **Effort:** S

### P3-043 — Leave / PTO request workflow
- **AC:** Agent requests; manager approves; auto-recompute schedule
- **Effort:** S

### P3-044 — Skill-based routing config
- **AC:** Tag agents with skills; route calls accordingly
- **Effort:** S

### P3-045 — Intraday adjustment
- **AC:** Mid-shift re-forecast; suggest schedule changes
- **Effort:** S

### P3-046 — Schedule swap (agent-to-agent)
- **AC:** Agent A requests swap with agent B; both confirm; manager approves
- **Effort:** S

---

## EPIC: Omnichannel ingestion

### P3-047 — WhatsApp Business API integration
- **AC:** Via Meta Cloud API or 360dialog; inbound messages route to agents; templated outbound; media support
- **Effort:** M

### P3-048 — Web chat widget
- **AC:** Embeddable JS; pre-chat form; live chat; co-browse optional
- **Effort:** M

### P3-049 — Email channel ingestion
- **AC:** IMAP poll per tenant inbox; SMTP send; thread by Message-ID; attach to contact
- **Effort:** M

### P3-050 — SMS inbound + outbound
- **AC:** Unifonic + Twilio; 2-way; templated outbound
- **Effort:** S

### P3-051 — Channel routing rules engine
- **AC:** Rules: WhatsApp from VIP → priority queue; emails containing "billing" → billing team
- **Effort:** S

### P3-052 — Unified agent inbox
- **AC:** Single UI showing all channels; agent picks up next item; chat-like UX
- **Effort:** L

### P3-053 — Customer profile / 360° view
- **AC:** Cross-channel history; recent interactions; sentiment; tags
- **Effort:** M

---

## EPIC: Mobile app

### P3-054 — Project setup (React Native)
- **AC:** iOS + Android builds; CI; push notifications via Firebase
- **Effort:** S

### P3-055 — Login + 2FA + biometric unlock
- **AC:** TOTP support; FaceID/TouchID/fingerprint
- **Effort:** S

### P3-056 — Wallboard view (mobile)
- **AC:** Live KPIs; agent status; queues
- **Effort:** M

### P3-057 — Real-time alerts via push
- **AC:** Fraud, SLA breach, quota threshold
- **Effort:** S

### P3-058 — WFM request approvals on the go
- **AC:** Approve/deny PTO + schedule swaps from phone
- **Effort:** S

### P3-059 — Recent calls + recording playback
- **AC:** Browse recent; listen to recording with transcript
- **Effort:** M

### P3-060 — Quick actions (disable extension, top-up wallet)
- **AC:** From mobile, in 2 taps
- **Effort:** S

### P3-061 — App Store + Play Store submission
- **AC:** Listings, screenshots, reviews flow; approved & live
- **Effort:** S

---

## EPIC: SSO + GDPR

### P3-062 — SAML 2.0 (Azure AD, Okta, OneLogin)
- **AC:** Per-tenant IDP config; SP metadata exposed; tested with each IDP
- **Effort:** M

### P3-063 — OIDC (Google, Azure AD)
- **AC:** Tenant configures; auto user provisioning
- **Effort:** S

### P3-064 — Just-in-time user provisioning
- **AC:** New user from SSO → auto-create with default role
- **Effort:** S

### P3-065 — GDPR data export per user
- **AC:** Customer requests → bundle of all data → ZIP delivered
- **Effort:** S

### P3-066 — Right-to-erasure workflow
- **AC:** Approve → cascade delete or anonymize; confirmation report
- **Effort:** S

### P3-067 — Consent logging
- **AC:** When recording starts, log opt-in/opt-out per call
- **Effort:** XS

---

## EPIC: Call quality monitoring

### P3-068 — Capture MOS / jitter / packet-loss from CDR
- **AC:** Where PBX provides (CUCM CMR, others); store in CallRecord
- **Effort:** S

### P3-069 — Quality dashboard
- **AC:** Per call / per route / per carrier; thresholds visualized
- **Effort:** S

### P3-070 — Carrier comparison
- **AC:** Side-by-side quality metrics
- **Effort:** S

### P3-071 — Threshold alerts
- **AC:** "Alert if MOS drops below 3.5 on any carrier in 10-min window"
- **Effort:** XS

### P3-072 — Codec usage analytics
- **AC:** % of calls per codec; quality per codec
- **Effort:** S

---

## EPIC: Compliance pack

### P3-073 — SAMA documentation pack
- **AC:** PDF document explaining how IPT Portal meets SAMA requirements; controls mapping
- **Effort:** S (compliance writer + legal review)

### P3-074 — CITC documentation pack
- **AC:** Similar
- **Effort:** S

### P3-075 — PDPL workflows
- **AC:** Consent capture, data export, deletion automation
- **Effort:** S

### P3-076 — Trust center page (public)
- **AC:** Public page listing certifications, controls, recent audits, contact
- **Effort:** S

### P3-077 — Vendor risk questionnaire library
- **AC:** Pre-filled answers to SIG, CAIQ, custom enterprise questionnaires
- **Effort:** S

### P3-078 — Annual pen-test + remediation
- **AC:** External vendor; report + remediation
- **Effort:** M

---

## EPIC: Custom report builder

### P3-079 — Drag-drop builder UI
- **AC:** Choose fields, filters, group-bys, sort; live preview
- **Effort:** L

### P3-080 — Save / share / schedule reports
- **AC:** Personal + team-shared; schedule email
- **Effort:** S

### P3-081 — Power BI connector
- **AC:** DirectQuery or Web Data Source; per-tenant credentials
- **Effort:** M

### P3-082 — Tableau Web Data Connector
- **AC:** WDC published
- **Effort:** S

### P3-083 — Looker connector
- **AC:** Configured for Looker
- **Effort:** S

### P3-084 — Generic read-only SQL endpoint
- **AC:** Postgres user with SELECT only; row-level security per tenant
- **Effort:** S

---

## EPIC: Trend / anomaly + journey analytics

### P3-085 — Trend detection on volumes / costs / sentiment
- **AC:** Daily / weekly trend cards; significant change alerts
- **Effort:** S

### P3-086 — Anomaly detection
- **AC:** Per-tenant baseline; alert on deviation
- **Effort:** M

### P3-087 — Sankey IVR flow visualization
- **AC:** Show call paths through IVR; identify drop-off points
- **Effort:** M

### P3-088 — Customer journey across channels
- **AC:** Timeline of all interactions for a contact
- **Effort:** M

---

## EPIC: Engagement tools

### P3-089 — Agent leaderboards
- **AC:** Configurable metrics; per team / company
- **Effort:** S

### P3-090 — Gamification: badges + points
- **AC:** Define badges; auto-award; agent profile shows
- **Effort:** S

### P3-091 — Manager nominations / recognition
- **AC:** Manager nominates agent; broadcast in-app + email
- **Effort:** XS

---

## Counts

| Epic | Tasks | Effort |
|---|---|---|
| Recording infra | 7 | ~3 weeks |
| Recording UI | 6 | ~2.5 weeks |
| Transcription pipeline | 6 | ~3 weeks |
| Sentiment / topic / summary | 6 | ~3 weeks |
| PCI / PII redaction | 5 | ~2 weeks |
| QA scorecards | 6 | ~3 weeks |
| Coaching | 3 | ~1 week |
| WFM-lite | 7 | ~5 weeks |
| Omnichannel | 7 | ~6 weeks |
| Mobile app | 8 | ~6 weeks |
| SSO + GDPR | 6 | ~2.5 weeks |
| Call quality | 5 | ~2 weeks |
| Compliance pack | 6 | ~2 weeks (+ external pen-test) |
| Custom report builder + BI | 6 | ~4 weeks |
| Trend / journey | 4 | ~3 weeks |
| Engagement | 3 | ~1 week |
| **Total** | **91** | **~50 weeks** |

With ~10 FTE × 24 weeks = 240 person-weeks available — comfortable margin for compliance audits, ML iteration, and bug-bash.
