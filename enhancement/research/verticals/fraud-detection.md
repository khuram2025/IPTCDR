# Vertical — Toll-Fraud / Telecom Fraud Detection

## Why ship this in Phase 1
- **Quick to build** (~2 weeks for MVP rule engine)
- **Standalone revenue line** ($300+/mo/customer benchmark via WebCDR)
- **Strong lead-gen tool** ("free toll-fraud audit" PDF)
- **Defensive product** — protects customers + protects us from "their PBX got hacked, why didn't your billing alert us"
- **Subex Telecom Fraud 2026 Report** confirms it's a strategic business risk for CSPs (EBITDA, customer trust, regulatory compliance, brand)

## Threat landscape (2026)
- Sophisticated attacks across voice, SMS, roaming, digital payments, IoT, 5G
- **Cloud SBC adoption expanded attack surface**
- **Inadequately isolated multi-tenant cloud PBX** enables cross-tenant abuse
- Common attack patterns:
  - **PBX hacking** (compromised SIP creds → outbound intl calls)
  - **Premium-rate destination calls** (satellite, certain countries)
  - **Late-night / weekend spike** (when admins not watching)
  - **Wangiri** (one-ring scams returning calls to premium)
  - **CLI spoofing for fraud**
  - **IRSF (International Revenue Share Fraud)**

## What to build (Phase 1 MVP)

### Rule engine — built-in rules
1. **International call spike** — N intl calls in T minutes
2. **After-hours intl** — intl calls outside business hours
3. **Premium destination** — calls to known premium prefixes
4. **Country blacklist** — calls to high-risk countries
5. **Velocity (per extension)** — calls/min, cost/hour, total duration/day
6. **Velocity (per company)** — aggregate cost spike
7. **New destination first call** — extension calls a country never called before
8. **Long-duration intl** — >30-min international call
9. **Concurrent calls** — extension making multiple simultaneous calls (often a sign of compromise)
10. **Failed-then-success** — many failed auths followed by success (brute force)

### Actions per rule
- Alert (email, SMS, Slack, Teams)
- Auto-disable extension
- Block route at SBC (advanced)
- Open ticket in connected ticketing system

### Severity levels
- Low / Medium / High / Critical
- Critical → auto-disable enabled by default

### Configuration UX
- Default rule pack seeded for new tenant
- Per-rule override (threshold, action, notification channels)
- Per-company customization (e.g., "this is a hotel, intl calls are normal")
- Shadow mode (alert only, don't block) for first 2 weeks per tenant

### Phase 3: ML enhancement
- Per-tenant baseline (normal pattern of calls)
- Anomaly score per call
- Auto-tune rule thresholds based on operator feedback (false-positive marking)
- Catches novel fraud patterns

## Free toll-fraud audit (lead gen)

**Mechanism:**
1. Public landing page → "Get a free toll-fraud audit of your CDRs"
2. Lead uploads CSV (or grants temp access to PBX)
3. Our engine runs rule pack against last 30-90 days
4. We generate **branded PDF report** with:
   - Total cost analyzed
   - Number of risky calls
   - Top 5 risk patterns found
   - Estimated savings if rules enforced
   - Recommended remediation
5. Email to lead + CRM follow-up
6. Convert to subscription

**Conversion lever:** "If you'd had IPT Portal active, this fraud would have been blocked, saving you SAR X."

## Pricing
- Add-on to base subscription: **SAR 199-499/mo** per tenant
- Standalone (no other product): **SAR 599-999/mo**
- Free fraud audit (PDF report): **always free** — pure lead gen

## Reference: WebCDR cloud fraud detection
- Pricing: from $300/mo
- Round-the-clock fraud protection with email + web alerts
- No on-site components or disruptive integration
- Confirms our pricing model & approach

## Reference: Tollring Protect
- Real-time fraud detection + revenue assurance
- Telecom-grade
- Bundled in Tollring Triple Play

## Reference: Subex
- Enterprise/CSP scale
- AI-first fraud prevention
- Confirms market direction

## Sources
- [Tollring Protect — Real-Time Fraud Detection](https://tollring.com/fraud-management)
- [WebCDR Cloud Fraud Detection](https://www.webcdr.com/explore-webcdr/anti-fraud)
- [VoIPmonitor Anti-Fraud](https://www.voipmonitor.org/doc/Anti-fraud)
- [Subex Telecom Fraud 2026 Report](https://www.subex.com/article/telecom-fraud-in-2026-types-emerging-risks-how-ai-first-prevention-stops-revenue-leakage/)
- [TransNexus VoIP Fraud Whitepaper](https://transnexus.com/whitepapers/introduction-to-voip-fraud/)
- [Variphy Toll Fraud Alert](https://www.variphy.com/voice/alert-possible-toll-fraud)
- [Toll Fraud Attacks in VoIP — Chakavak](https://chakavak.io/en/toll-fraud-attacks-in-voip-and-how-to-prevent-them/)
- [VoIP Fraud Prevention Guide — MultaHost (VOS3000)](https://multahost.com/blog/voip-fraud-prevention-2/)
- [VOS3000 Illegal Call Recording / Unauthorized IP Detection](https://multahost.com/blog/vos3000-illegal-call-recording/)
