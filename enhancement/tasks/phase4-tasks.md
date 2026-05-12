# Phase 4 — Granular Task List (Months 12-18)

---

## EPIC: CRM connectors

### P4-001 — Salesforce managed package on AppExchange
- **AC:** Listed on AppExchange; security review passed; installable; OAuth flow tested
- **Effort:** L (12+ weeks counting AppExchange review)

### P4-002 — Salesforce: click-to-call + screen pop + call logging + recording link
- **AC:** Each feature working in classic + Lightning; Apex code minimal
- **Effort:** M

### P4-003 — HubSpot marketplace app
- **AC:** Published; OAuth; same feature set as Salesforce
- **Effort:** M

### P4-004 — Zoho CRM extension
- **AC:** Published in Zoho Marketplace
- **Effort:** S

### P4-005 — Bitrix24 integration (REST API)
- **AC:** Module published in Bitrix24 marketplace
- **Effort:** S

### P4-006 — Odoo module
- **AC:** Published on Odoo Apps; v16 + v17
- **Effort:** S

### P4-007 — Microsoft Dynamics 365 connector
- **AC:** Power Platform connector OR custom plugin
- **Effort:** M

### P4-008 — Pipedrive marketplace app
- **AC:** Published; same feature set
- **Effort:** S

---

## EPIC: Help-desk integrations

### P4-009 — Zendesk (ticket sync, recording attachment, agent context)
- **AC:** App published in Zendesk Marketplace; tested
- **Effort:** M

### P4-010 — Freshdesk integration
- **AC:** Marketplace listing; tested
- **Effort:** S

### P4-011 — Intercom integration
- **AC:** Marketplace listing; tested
- **Effort:** S

---

## EPIC: AI voice agent

### P4-012 — Dialog manager core
- **AC:** LLM-driven turn management; intent classification; slot filling
- **Effort:** L

### P4-013 — Multi-language model selection
- **AC:** Auto-detect language; route to appropriate STT/TTS/LLM; supports AR, EN, UR, HI, TL
- **Effort:** M

### P4-014 — Inbound IVR replacement
- **AC:** Replace tree-based IVR with conversational agent; intents → fulfillment functions
- **Effort:** L

### P4-015 — Outbound campaign engine
- **AC:** List → call schedule → bot dials → conversation → outcomes captured
- **Effort:** L

### P4-016 — FAQ deflection bot
- **AC:** Knowledge base ingestion; bot answers from KB; falls back to human
- **Effort:** M

### P4-017 — Appointment booking bot
- **AC:** Calendar integration (Google / Outlook / Calendly); books slot in conversation
- **Effort:** M

### P4-018 — Voice-to-CRM
- **AC:** Bot conversation → structured fields → push to CRM record
- **Effort:** S

### P4-019 — Bot → human handoff
- **AC:** Trigger handoff (intent: "speak to agent" or low confidence); transfer call with full transcript context
- **Effort:** M

### P4-020 — Custom voice cloning (premium)
- **AC:** Customer provides voice samples; clone via ElevenLabs / similar; use in TTS
- **Effort:** M

### P4-021 — Per-minute billing + caps
- **AC:** Meter usage; enforce caps; alert customer
- **Effort:** S

---

## EPIC: Predictive / power dialer

### P4-022 — Predictive dialer engine
- **AC:** Ratio-based pacing; learns from connect rates; <3% abandonment
- **Effort:** L

### P4-023 — Power dialer (1:1 agent-paced)
- **AC:** Click-next dials next contact; agent always available
- **Effort:** M

### P4-024 — Preview dialer
- **AC:** Show contact, agent reviews, clicks dial
- **Effort:** S

### P4-025 — Answering machine detection (AMD)
- **AC:** ML-based AMD; <5% false positives
- **Effort:** M

### P4-026 — Voicemail drop
- **AC:** Pre-recorded message; auto-played on AMD detection
- **Effort:** S

### P4-027 — DNC management
- **AC:** Import DNC lists; cross-check before each call; per-tenant + global lists
- **Effort:** S

### P4-028 — Time-zone aware dialing
- **AC:** Detect zone from number / contact; only dial in allowed hours per region
- **Effort:** S

### P4-029 — Abandonment rate enforcement
- **AC:** Track 30-day rolling abandonment; auto-throttle if approaches 3%
- **Effort:** S

### P4-030 — Campaign management dashboard
- **AC:** Create campaign, assign list, set hours, monitor progress, dispositions
- **Effort:** M

### P4-031 — Lead list management
- **AC:** Import CSV → dedupe → segment → assign to campaign
- **Effort:** S

---

## EPIC: DID / number management

### P4-032 — DID inventory
- **AC:** All numbers with status (assigned/available/quarantined/ported-out)
- **Effort:** S

### P4-033 — Port-in workflow
- **AC:** LOA upload, RespOrg/carrier coordination, status tracking
- **Effort:** M

### P4-034 — Port-out workflow
- **AC:** Customer-initiated; admin approval; carrier coordination
- **Effort:** S

### P4-035 — Vanity number search
- **AC:** Search "*-CARS" or "1234*" patterns from inventory
- **Effort:** S

### P4-036 — Number assignment to extensions / queues / IVR
- **AC:** Drag-drop or form; history of assignments
- **Effort:** S

### P4-037 — Carrier integration (DIDWW, Voxbone, local KSA carriers)
- **AC:** API ingestion of available DIDs; auto-purchase; auto-assign
- **Effort:** M

---

## EPIC: Carrier / SBC integration

### P4-038 — SBC log ingestion (Asterisk/Kamailio/Sansay)
- **AC:** Configurable per tenant; SIP messages stored for troubleshooting
- **Effort:** M

### P4-039 — Auto-failover routing rules
- **AC:** If carrier X has high jitter or 5xx rate, route to carrier Y
- **Effort:** M

### P4-040 — Carrier rate-card sync (auto-import)
- **AC:** Pull from carrier API or scheduled SFTP
- **Effort:** S

---

## EPIC: Multi-entity billing + CPQ

### P4-041 — Parent/child organization model
- **AC:** Parent org has multiple child companies; consolidated billing
- **Effort:** S

### P4-042 — Consolidated invoicing
- **AC:** Parent invoice rolls up child usage
- **Effort:** S

### P4-043 — Inter-company chargeback
- **AC:** Cost allocation between child entities; reports
- **Effort:** S

### P4-044 — CPQ workflow
- **AC:** Sales team configures quote → approval workflow → e-sign → auto-provision
- **Effort:** M

---

## EPIC: Cross-tenant benchmarking

### P4-045 — Anonymized aggregations
- **AC:** Industry / region / size benchmarks; opt-in
- **Effort:** S

### P4-046 — Peer benchmarks UI
- **AC:** "Your AHT is 15% higher than industry median for banking in KSA"
- **Effort:** S

### P4-047 — Privacy guarantees (k-anonymity)
- **AC:** Min 5 tenants per cohort; no individual-tenant disclosure
- **Effort:** S

---

## EPIC: Real-time RTP monitoring

### P4-048 — RTP capture from SBC
- **AC:** Pcap stream or VoIPmonitor integration
- **Effort:** M

### P4-049 — Live MOS calculation
- **AC:** Per-call MOS shown live during call
- **Effort:** S

### P4-050 — One-way audio detection
- **AC:** Alert when RTP flow asymmetric > N seconds
- **Effort:** S

### P4-051 — Codec mismatch alerts
- **AC:** Detect codec renegotiation; correlate with quality drop
- **Effort:** S

---

## EPIC: Multi-region data residency

### P4-052 — Terraform per region
- **AC:** Reproducible deploy in AWS me-central-1, me-south-1, eu-west-1
- **Effort:** M

### P4-053 — Tenant region attribute + edge routing
- **AC:** Tenant created in region; CloudFront / Route 53 routes to correct origin
- **Effort:** M

### P4-054 — Per-region control plane (small) replicated
- **AC:** Auth, billing metadata replicated; data plane fully isolated
- **Effort:** M

### P4-055 — Tenant migration tool (region A → B)
- **AC:** Coordinated migration with downtime window; data integrity verified
- **Effort:** L

---

## EPIC: SOC 2 Type II + ISO 27001 + PCI DSS

### P4-056 — Continuous compliance tooling (Drata / Vanta / Secureframe)
- **AC:** Tool deployed; controls auto-monitored; evidence collected
- **Effort:** M

### P4-057 — SOC 2 Type II audit
- **AC:** 6-month evidence period; auditor engagement; report obtained
- **Effort:** L (calendar time)

### P4-058 — ISO 27001 certification audit
- **AC:** Stage 1 + Stage 2 audits passed; certificate issued
- **Effort:** L

### P4-059 — PCI DSS attestation
- **AC:** SAQ A or D depending on scope; attestation issued
- **Effort:** M

---

## EPIC: Multi-channel WFM (advanced)

### P4-060 — Multi-channel forecasting
- **AC:** Voice + chat + email weighted; per-skill forecast
- **Effort:** M

### P4-061 — What-if scenario planning
- **AC:** "What if call volume up 20%?" → suggested staffing
- **Effort:** S

### P4-062 — Calendar sync (Google / Outlook)
- **AC:** Two-way sync of agent schedule
- **Effort:** S

### P4-063 — Schedule swap workflow
- **AC:** Agent A↔B; both confirm; manager approves
- **Effort:** S

---

## EPIC: Vertical bundles

### P4-064 — IPT Bank (KSA banking)
- **AC:** SAMA enabled, PCI redaction, banking IVR templates, FATF screening, banking-specific reports
- **Effort:** M (per bundle)

### P4-065 — IPT Health (clinic / hospital)
- **AC:** Appointment bot, telemedicine integration, HIPAA-aligned controls, healthcare KPIs
- **Effort:** M

### P4-066 — IPT Hospitality (hotels)
- **AC:** PMS integration (Opera, Mews, Cloudbeds), guest service routing, multi-language
- **Effort:** M

### P4-067 — IPT Government
- **AC:** Arabic-first UI, accessibility (WCAG 2.1 AA), citizen survey bot, in-Kingdom data residency
- **Effort:** M

---

## EPIC: Generic SQL export

### P4-068 — Read-only Postgres replica per tenant
- **AC:** Per-tenant credentials; row-level security; documentation
- **Effort:** S

### P4-069 — BigQuery / Snowflake / Redshift connector
- **AC:** Fivetran-style scheduled exports OR live connector
- **Effort:** M

---

## EPIC: Additional PBX adapters

### P4-070 — Avaya CDR adapter
- **AC:** Aura / IP Office support
- **Effort:** M

### P4-071 — Mitel adapter
- **AC:** Several Mitel platforms supported
- **Effort:** M

### P4-072 — RingCentral adapter
- **AC:** Via RingCentral API
- **Effort:** S

### P4-073 — Vonage adapter
- **AC:** Via Vonage API
- **Effort:** S

### P4-074 — 8x8 adapter
- **AC:** Via 8x8 API
- **Effort:** S

---

## EPIC: ML fraud anomaly detection

### P4-075 — Per-tenant baseline training
- **AC:** Train on 30+ days of CDR; learns normal patterns
- **Effort:** M

### P4-076 — Anomaly score per call
- **AC:** Real-time inference; score combined with rule-based engine
- **Effort:** S

### P4-077 — Auto-tune thresholds
- **AC:** Reduce false positives over time based on operator feedback
- **Effort:** S

---

## EPIC: DLP for recordings

### P4-078 — Sensitive info detection in transcripts
- **AC:** Detect verbal share of password, full SSN, etc.
- **Effort:** M

### P4-079 — Auto-redact post-detection
- **AC:** Redact transcript + audio; alert security team
- **Effort:** S

---

## Counts

| Epic | Tasks | Effort |
|---|---|---|
| CRM connectors | 8 | ~12 weeks (parallel) |
| Help-desk | 3 | ~3 weeks |
| AI voice agent | 10 | ~12 weeks |
| Predictive / power dialer | 10 | ~8 weeks |
| DID / number management | 6 | ~4 weeks |
| Carrier / SBC | 3 | ~3 weeks |
| Multi-entity + CPQ | 4 | ~3 weeks |
| Cross-tenant benchmarking | 3 | ~2 weeks |
| Real-time RTP | 4 | ~3 weeks |
| Multi-region | 4 | ~6 weeks |
| Compliance certifications | 4 | ~6 weeks (+ external) |
| Multi-channel WFM advanced | 4 | ~3 weeks |
| Vertical bundles | 4 | ~8 weeks |
| Generic SQL | 2 | ~2 weeks |
| Additional PBX adapters | 5 | ~6 weeks |
| ML fraud | 3 | ~3 weeks |
| DLP for recordings | 2 | ~2 weeks |
| **Total** | **79** | **~86 weeks** |

With ~14 FTE × 24 weeks = 336 person-weeks — accounts for compliance lead-time, App Store review delays, customer pilots, and parallel CRM/dialer/voice-agent epics.
