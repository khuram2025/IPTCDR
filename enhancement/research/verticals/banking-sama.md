# Vertical — Banking & SAMA Compliance (KSA)

## Why this vertical
- KSA banks are a **massive, well-funded** market (~30 commercial banks + Islamic + insurance + brokerages)
- Strict regulator (SAMA) creates **clear compliance requirements** = clear product features = clear sales hook
- US/EU vendors don't have **SAMA-specific certifications** out of the box — local moat
- Avg deal size: SAR 50,000-500,000+/year per bank

## SAMA-specific requirements

### Record retention
- **Banks must retain records for at least 10 years** (Article 12 SAMA Rulebook)
- Original paper records or electronic copies authenticated by bank stamp
- Annual periodic review by Internal Audit to verify integrity
- After 10 years, electronic storage permitted with secure preservation

### Customer information
- Banks must inform customers about retention period via contracts and website

### AML/CTF (Anti-Money Laundering / Counter-Terrorism Financing)
- Customer identification (KYC)
- Continuous transaction monitoring
- Record retention
- Escalation procedures for suspicious transactions
- Sanctions screening (FATF, OFAC, local lists)

### Cybersecurity (NCA-aligned)
- Encryption at rest + in transit
- Access controls + audit logs
- Multi-factor authentication
- Vulnerability management
- Incident response

### Data residency
- Sensitive customer data **should be stored in-Kingdom** (per CITC + NCA + SAMA expectations)
- Cloud hosting must use approved providers with KSA region

## What our product needs to ship for banking buyers

### IPT Bank bundle features
1. **Recording with 10-year retention** — automated lifecycle, immutable storage, certified backups
2. **Tamper-evident audit trail** — cryptographic hash chain on each recording
3. **Per-recording access log** — who listened, when, why
4. **PCI redaction** — auto-mute card numbers, CVV
5. **Banking PII redaction** — Saudi National ID, IBAN
6. **Sanctions screening hook** — IVR or transcript triggers FATF/OFAC check
7. **Mandatory disclosure detection** — "agent must read terms before transaction" QA scorecard
8. **In-Kingdom data residency** — STC Cloud or Mobily Cloud option
9. **Bilingual** (Arabic + English) for customer-facing & internal use
10. **SAMA-compliant access reports** — pre-built for auditors
11. **Annual integrity verification report** — automated, sent to Internal Audit
12. **NCA ECC-1:2018 controls mapping** — documentation for cyber audit

### Pricing
- Recording Compliance Bundle: **+SAR 1,500-5,000/mo flat** per company on top of base tier
- Justified by 10-yr retention infra + audit features + SAMA documentation
- Often paid as part of base ContactPro tier with banking template

### Sales motion
- Direct enterprise sales + KSA SI partners with SAMA experience
- Lead-magnet: "**SAMA Recording Compliance Gap Analysis**" — free 1-day assessment of bank's current setup
- Reference selling: 2-3 reference accounts unlock the rest of the market
- Procurement: long cycles (6-12 months); engage IT + Risk + Compliance + Procurement

## Other regulators
- **CMA (Capital Market Authority)** — for brokerages / asset management
- **ZATCA** — VAT, e-invoicing
- **CST (formerly CITC)** — telecom licensing

## Banking call-flow patterns we should template

| Use case | Flow |
|---|---|
| Account inquiry | IVR → authentication → balance / transaction history → resolution |
| Card block / fraud | High-priority routing → fraud team → recording mandatory + extra retention |
| Loan application | Sales queue → call recording with disclosure → CRM logged |
| Complaint handling | Dedicated queue → SLA-tracked → escalation matrix → customer satisfaction survey |
| Wealth management | VIP routing → relationship manager → encrypted recording |

## Sources
- [SAMA Record Retention Article 12](https://rulebook.sama.gov.sa/en/article-12-record-retention)
- [SAMA Record Retention Guidelines](https://rulebook.sama.gov.sa/en/record-retention-guidelines)
- [SAMA Documentation & Record Keeping](https://rulebook.sama.gov.sa/en/instructions-documentation-and-record-keeping)
- [SAMA Compliance Principles for Banks](https://rulebook.sama.gov.sa/en/principles-compliance-commercial-banks-operating-kingdom-saudi-arabia)
- [SAMA Preservation of Customer Documents](https://www.rulebook.sama.gov.sa/en/preservation-documents-related-bank-customers)
- [Saudi Central Bank AML/CTF Framework — Facctum](https://www.facctum.com/terms/saudi-central-bank-sama)
- [SAMA Compliance — Cloud4C](https://www.cloud4c.com/cybersecurity-services/sama-compliance)
- [SAMA Compliance — Google Cloud](https://cloud.google.com/security/compliance/sama)
- [SAMA Compliance — Jetico](https://jetico.com/saudi-arabian-monetary-authority-sama-compliance/)
- [Kiteworks for KSA Financial Compliance](https://www.kiteworks.com/brief-kiteworks-solutions-for-safeguarding-data-and-enforcing-access-control-in-saudi-arabia-to-enhance-financial-compliance/)
