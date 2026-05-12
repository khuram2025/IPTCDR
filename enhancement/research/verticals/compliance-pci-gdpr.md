# Vertical — Compliance: PCI / GDPR / SAMA / MiFID / HIPAA / KSA PDPL

## Why this matters
- **GDPR fines totaled €1.2B+ in 2025**; non-compliance is existential
- KSA PDPL (Personal Data Protection Law) is the new local equivalent
- Banks (SAMA) and healthcare (HIPAA-style) require strict recording controls
- **Compliance certifications gate enterprise procurement** — without them, you can't sell

## Frameworks we must align with

### KSA PDPL (Personal Data Protection Law)
- Effective Sep 2024 with enforcement now active
- Requires consent, purpose limitation, data subject rights, breach notification
- Data localization preferences
- Penalties up to SAR 5M

### SAMA (Saudi banking)
- See `banking-sama.md`
- 10-year retention
- Cybersecurity controls

### CITC / CST (Saudi telecom)
- Telecom licensing compliance
- International call routing rules

### NCA (Saudi National Cybersecurity Authority)
- ECC-1:2018 (Essential Cybersecurity Controls)
- For critical infrastructure + government

### GDPR (EU)
- Consent for recording + processing
- Right to access, erasure, portability
- Data Protection Officer (DPO)
- 72-hour breach notification
- Fines up to €20M or 4% revenue

### PCI DSS (payments)
- Card data must never be stored unencrypted
- Auto-detect + redact card numbers + CVV
- Pause/resume controls
- Strict access controls

### MiFID II (EU financial)
- Phone recordings for trades/investments retained ~5 years
- Tamper-evident

### HIPAA (US healthcare — adopted in spirit by KSA hospitals)
- PHI protection
- BAA (Business Associate Agreement) with vendors
- Encryption + access controls

### SOC 2 Type II
- US enterprise procurement gate
- 6 months evidence period
- Annual audit
- Type I = point-in-time, Type II = sustained controls

### ISO 27001
- International information security standard
- 3-year cycle (initial + 2 surveillance)
- Recognized globally

## What customers ask for in RFPs

| Question | Answer |
|---|---|
| Where is data stored? | "Per-tenant region selection. KSA tenants on STC Cloud or AWS me-central-1." |
| Encryption at rest? | "Yes, AES-256 with per-tenant KMS keys, customer-managed keys (BYOK) optional" |
| Encryption in transit? | "Yes, TLS 1.3, mTLS between services" |
| Recording PCI redaction? | "Yes, automatic DTMF mute + transcript regex redaction" |
| Recording retention configurable? | "Yes, per-company + per-recording" |
| Right to erasure workflow? | "Yes, customer self-serve + admin approval workflow" |
| Audit logs? | "Yes, immutable, accessible to customer for self-audit" |
| Pen-test reports available? | "Yes, annual external pen-test, executive summary shared under NDA" |
| SOC 2 / ISO 27001? | "SOC 2 Type II in progress (Q3 2027); ISO 27001 in progress (Q4 2027)" |
| Sub-processors disclosed? | "Yes, public list maintained at /trust/subprocessors" |

## What to build (Phase 3 + Phase 4)

### Phase 3 (compliance foundations)
- **Trust center** page (public) listing certifications, controls, sub-processors
- **Audit log** for all state-changes
- **Encryption at rest** (per-tenant KMS)
- **Recording retention** policies + automation
- **PCI redaction** (DTMF + regex)
- **PII redaction** (KSA National ID, IBAN, etc.)
- **Consent logging** for recordings
- **GDPR data export** per user
- **Right to erasure** workflow
- **Vendor risk questionnaire library** (SIG, CAIQ, custom)
- **Annual pen-test** (external vendor)
- **SAMA documentation pack** (banking)
- **CITC documentation pack** (telecom)

### Phase 4 (certifications)
- **SOC 2 Type II** audit
- **ISO 27001** certification audit
- **PCI DSS attestation**
- **NCA ECC-1:2018** alignment for govt customers
- **Continuous compliance** tooling (Drata / Vanta / Secureframe)
- **Data residency selector** (KSA, UAE, EU)

## Recording compliance specifically

### Required features
- **Multiple recording modes** (Always-On / On-Demand / Selective per call type)
- **Encryption at rest** (AES-256, per-tenant KMS)
- **Retention policies** per company / per recording
- **Tamper-evident storage** (hash chain or WORM storage)
- **Per-recording access log** (who listened, when)
- **Auto-deletion at expiry**
- **Right-to-erasure workflow**
- **Consent capture** at call start (announcement + opt-in)
- **PCI/PII redaction** (auto)
- **Pause/resume controls** (manual)
- **Search recordings** (transcript-based)
- **Sharing with signed URLs** (time-limited, role-restricted)

### Industry retention defaults
- Banking (SAMA): 10 years
- Healthcare: 7 years (clinical), 3 years (admin)
- Trading/MiFID: 5 years
- General: 3-5 years (configurable)

## Reference vendors / platforms
- **CallCabinet** — cloud-native compliance recording
- **Smartcall** — PCI-compliant recording
- **Imagicle Call Recording** — GDPR/MiFID/HIPAA-aligned
- **Kiteworks** — KSA financial compliance
- **Drata / Vanta / Secureframe** — continuous compliance tooling for SOC 2

## Sources
- [Call Recording Compliance Guide 2026 — PBX.IM](https://www.pbx.im/blog/call-recording-compliance-guide)
- [What is Call Recording Compliance — CallCabinet](https://www.callcabinet.com/blog/what-is-call-recording-compliance/)
- [GDPR Compliant Call Recording Solutions 2026 — Sybill](https://www.sybill.ai/blogs/gdpr-compliant-call-recording-solutions)
- [PCI Compliant Call Recording — Smartcall](https://www.smartcall.com/pci-compliance-options/)
- [PCI-Compliant VoIP Call Recording — VoIPShop](https://www.thevoipshop.co.uk/pci-compliant-call-recording)
- [HIPAA, PCI, GDPR Compliant AI Voice Recording](https://markets.financialcontent.com/stocks/article/marketersmedia-2026-4-1-hipaa-pci-gdpr-compliant-ai-voice-recording-voice-data-guide-published)
- [Cloud-Native Compliance Call Recording — CallCabinet](https://www.callcabinet.com/cloud-native-compliance-call-recording/)
- [GDPR & Call Recording Compliance Help](https://connection-technologies.co.uk/help/voip-security/gdpr-call-recording-compliance)
- [PCI Compliant Call Recording: 5 Essentials — Paytia](https://www.paytia.com/resources/blog/5-essential-tips-for-pci-compliant-phone-payments)
- [Call Recording in 2026: Use Cases & Features — Imagicle](https://www.imagicle.com/en/blog/customer-experience/cx-software-enterprise/call-recording-use-cases-features/)
- [SAMA Compliance — Cloud4C](https://www.cloud4c.com/cybersecurity-services/sama-compliance)
- [Kiteworks for KSA Financial Compliance](https://www.kiteworks.com/brief-kiteworks-solutions-for-safeguarding-data-and-enforcing-access-control-in-saudi-arabia-to-enhance-financial-compliance/)
