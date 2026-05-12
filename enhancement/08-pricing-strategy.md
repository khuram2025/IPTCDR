# Pricing & Packaging Strategy

---

## Subscription tiers (per tenant, per month)

### IPT Bill (Billing & rating)

| Tier | Price (SAR) | Extensions | Includes |
|---|---|---|---|
| Starter | 499 | up to 50 | 1 PBX, basic rate cards, monthly invoices |
| Business | 1,499 | up to 250 | + multi-PBX (2), LCR, prepaid+postpaid, fraud alerts (basic) |
| Pro | 3,999 | up to 1,000 | + LCR multi-carrier, white-label, advanced fraud, SLA reports |
| Enterprise | Custom | 1,000+ | + multi-entity, dedicated CSM, custom integrations |

### IPT Insight (Analytics & wallboards)

| Tier | Price (SAR) | Includes |
|---|---|---|
| Starter | 999 | dashboards, top-extension, country reports, exports |
| Business | 1,999 | + real-time wallboards (1 screen), custom reports, scheduled emails |
| Pro | 4,999 | + drag-drop wallboards (multi-screen), Power BI/Tableau, KPI library, SLA breaches |
| Enterprise | Custom | + cross-tenant benchmarking, white-label dashboards |

### IPT Contact (AI contact center)

| Tier | Price | Includes |
|---|---|---|
| Voice | SAR 89/agent/mo | basic queue + agent dashboard + recording + 100 transcription min/agent |
| Voice + AI | SAR 149/agent/mo | + sentiment + topic spotting + summaries + auto-QA + 500 STT min/agent |
| Omnichannel | SAR 189/agent/mo | + WhatsApp + chat + email + SMS + unified inbox |
| WFM Add-on | +SAR 49/agent/mo | forecasting + scheduling + adherence |
| Recording Compliance Bundle | +SAR 1,500/mo flat per company | SAMA 10-yr retention + PCI/PII redaction + audit trail |

### Bundle (all 3 lines)

| Bundle | Discount |
|---|---|
| Bill + Insight | 15% off combined |
| Bill + Insight + Contact | 25% off combined |

---

## Usage-based pricing

| Item | Price | Cost (estimated) | Margin |
|---|---|---|---|
| AI minutes (English transcription) | SAR 0.10/min | ~SAR 0.04 | 60% |
| AI minutes (Arabic transcription) | SAR 0.20/min | ~SAR 0.08 | 60% |
| AI minutes (real-time streaming) | SAR 0.40/min | ~SAR 0.15 | 62% |
| Recording storage (cold, S3 Glacier) | SAR 0.50/GB/mo | ~SAR 0.02 | 96% |
| Recording storage (hot, S3) | SAR 2.00/GB/mo | ~SAR 0.08 | 96% |
| AI voice agent minute | SAR 1.50/min | ~SAR 0.50 | 67% |
| WhatsApp Business conversation | SAR 0.20/conv | varies (Meta: $0.005-0.07) | 70% |
| SMS (KSA inbound) | SAR 0.15/msg | varies | 70% |
| Outbound carrier minutes | per rate-card | per carrier | 10-30% |

---

## Add-ons & modules (flat monthly)

| Add-on | Price (SAR/mo) |
|---|---|
| Toll-fraud protection (advanced rules + ML) | 299 |
| Custom report builder | 499 |
| CRM connector (per CRM) | 199-499 |
| Power BI / Tableau / Looker connector | 499 |
| Mobile app (per company) | 0 (included) for Business+ |
| Dedicated KSA data residency | +30% on base |
| Premium support / 24x7 SLA | +15% on base |
| Onboarding & migration (one-time) | 5,000-25,000 |
| Custom integration project | 25,000-150,000 |
| Compliance audit advisory | 25,000-100,000 |

---

## Reseller / White-Label

| Component | Pricing |
|---|---|
| Platform fee | SAR 5,000-15,000/mo (depends on tenant cap) |
| Revenue share | Reseller keeps 60-70%, we keep 30-40% |
| Branding | Custom domain, logo, colors, email templates included |
| Tenant cap | 25-100 tenants depending on tier |
| Onboarding | First 5 tenants onboarded free; 6+ at SAR 1,500 each |

---

## Free tier / trial strategy

- **14-day free trial** of any tier (Starter/Business/Pro), no credit card required
- **Always-free reports:**
  - Free toll-fraud audit (one-shot 7-day report) — lead-gen tool
  - Free monthly cost-summary email (anonymous-aggregated)
- **Freemium for individual extensions** (developer / hobbyist tier): 1 PBX, ≤10 extensions, basic dashboard, no exports

---

## Comparison table for sales

(Use in pitches: "look how much we save you")

| Capability | IPT Portal Pro | Variphy + Tollring + Imagicle | Stand-alone tools (CloudTalk + Calabrio + WebCDR + Stripe) |
|---|---|---|---|
| Multi-PBX | ✅ | ✅ | ❌ |
| Billing + invoicing | ✅ | ❌ | partial |
| Wallboards | ✅ | ✅ | ✅ |
| Recording + AI | ✅ | ✅ | ❌ |
| Fraud detection | ✅ | ✅ (Tollring Protect) | ✅ (WebCDR) |
| Arabic UI | ✅ | ❌ | ❌ |
| MENA payment gateways | ✅ | ❌ | ❌ |
| MENA support hours | ✅ | ❌ | ❌ |
| **Approx monthly cost (250 ext + 50 agents)** | **~SAR 8,000** | **~SAR 25,000+** | **~SAR 18,000+** |

---

## Discounts

- Annual prepay: **15% off**
- Multi-year (2-3yr): **20-25% off**
- Charity / education: **30% off**
- Government: case-by-case
- Channel partner deal-reg: **20% off** (passed to partner as commission)

---

## Currency & localization in pricing

| Region | Display currency | Tax | Local payment |
|---|---|---|---|
| Saudi Arabia | SAR | VAT 15% | Mada, HyperPay, Tap, STC Pay |
| UAE | AED | VAT 5% | PayTabs, Tap, Network |
| Egypt | EGP | VAT 14% | PayTabs, Fawry |
| Qatar / Bahrain / Kuwait / Oman | local | local VAT | local gateways |
| Pakistan | PKR | sales tax 18% | JazzCash, Easypaisa |
| Default international | USD | none | Stripe |

---

## Pricing experiments to run

1. **Q1 2027:** Test annual prepay vs. monthly conversion lift
2. **Q1 2027:** A/B test "free fraud audit" CTA vs. "free trial" CTA on landing page
3. **Q2 2027:** Test bundle discount 25% vs. 30% — measure attach rate
4. **Q3 2027:** Test per-agent vs. flat-tenant pricing for Contact line
5. **Q4 2027:** Test usage caps vs. unlimited at higher price

---

## Contract terms

- **Standard:** monthly, no commitment, 30-day cancellation notice
- **Annual:** 15% off, locked-in pricing
- **Enterprise:** 3-year MSA with annual price escalator (3-5%)
- **SLA:** 99.5% uptime standard; 99.9% on Pro; 99.95% on Enterprise + premium-support add-on
- **Data export** (for churn): customer can export all CDR + recordings + invoices for 90 days post-cancellation

---

## Key pricing principles

1. **Per-tenant base + per-agent for Contact line** — aligns price with value
2. **Usage add-ons are 60-95% margin** — protects gross margin as customers grow
3. **Bundle discounts reward expansion** — drives ACV upgrades
4. **Local currency + local payment** — eliminates a procurement objection
5. **Free fraud audit** — converts cold leads at industry-best rates ($300+/mo product per WebCDR benchmark)
6. **Reseller rev-share at 60-70%** — meaningful for partners; matches Viirtue / IntuPBX models
