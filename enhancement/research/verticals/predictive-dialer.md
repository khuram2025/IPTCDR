# Vertical — Predictive / Power Dialer (Outbound)

## Why this matters
- **Egypt + Cairo BPO market** is huge and growing — outbound campaign vendors are the largest customer category
- KSA / UAE financial services do collections + sales outreach
- Standalone product line + add-on to Contact tier

## Dialer types

### Predictive
- System predicts agent availability + dials multiple numbers ahead
- Maximizes agent talk-time
- **Risk:** dropped calls if no agent available → must stay <3% abandonment per TCPA

### Power
- 1:1 — system dials when agent is free
- No abandonment risk
- Lower productivity than predictive

### Preview
- Show contact to agent first, agent clicks to dial
- High-touch sales (B2B, enterprise)

### Progressive
- Like power but agent doesn't get to preview before dial

## Required features

### Compliance
- **DNC (Do Not Call) list management** — import federal/state/private lists; auto-scrub before each call
- **TCPA compliance** (US) / **CITC compliance** (KSA) — depending on market
- **Time-zone aware dialing** — only dial in allowed hours per region
- **Abandonment rate enforcement** — auto-throttle approaching 3% (FTC mandate)
- **Consent prompts** — recording disclosure
- **Audit logs**

### Productivity
- **Answering Machine Detection (AMD)** — skip voicemail or play voicemail-drop
- **Voicemail drop** — pre-recorded message
- **Call dispositions** (sale, callback, not interested, wrong number, etc.)
- **Click-next dialing** (power mode)
- **Live agent assist** (real-time scripts, prompts)
- **Call scripting** — guided conversation
- **Call monitoring + barge / whisper / coach**
- **Lead scoring** — prioritize hot leads
- **Adjustable call pacing**

### Campaign management
- Create campaign with list + script + hours + caller ID + agent group
- Real-time progress dashboard
- Disposition reports
- Conversion attribution
- A/B test scripts / caller IDs

### Integration
- CRM sync (push dispositions, log calls)
- Calendar (callback scheduling)
- Payment (collections — take card on call)

## What to build (Phase 4)

### MVP
- Predictive + power + preview modes
- AMD
- Voicemail drop
- DNC management
- Time-zone aware
- Abandonment enforcement
- Campaign dashboard
- Lead list import + dispositioning
- Agent screen pop with lead context

### v2
- Lead scoring (ML)
- A/B test framework
- CRM deep integrations
- Live agent assist with AI suggestions

## Pricing
- Add-on to Contact tier: **+SAR 99-149/agent/mo**
- **+ Carrier minutes pass-through**
- Often customers also need: SIP trunk → can resell or bundle with our LCR engine

## MENA market notes
- KSA: outbound regulated by **CST (formerly CITC)** — calling hours, consent, ID display
- Egypt: BPO export market (call centers serving US/EU/GCC) — TCPA compliance critical
- UAE: financial services collections + sales

## Reference vendors
- **Convoso** — strong predictive dialer, SMB-friendly
- **TCN** — predictive
- **CallTools** — TCPA-focused
- **Vicidial / GoAutoDial** — open source (low-cost competitor)
- **ICTBroadcast** — TCPA-compliant
- **Platform28** — TCPA tools built-in
- **Voiso** — modern UX
- **Sales Sling** — TCPA + CRM-integrated
- **Five9** — enterprise
- **NICE inContact** — enterprise

## Differentiation
- **Bundled with our analytics + recording + AI** + LCR engine + carrier
- **MENA-aware compliance** (CST + local rules)
- **Arabic/English script support** for outbound campaigns
- **Lower TCO** than Five9 / NICE
- **AI voice agent** (Phase 4) can replace dialer agents for some use cases (surveys, confirmations)

## Sources
- [Importance of TCPA Compliance for Predictive Dialers — CallTools](https://calltools.com/blog/importance-of-tcpa-compliance-for-predictive-dialers/)
- [Predictive Dialer Software & System for Contact Centers — TCN](https://www.tcn.com/contact-center-solutions/predictive-dialer/)
- [TCPA Compliant Predictive Dialer — ICTBroadcast](https://www.ictbroadcast.com/ictbroadcast-tcpa-compliant-predictive-dialer-call-center-software/)
- [Best Predictive Dialer Software 2026 — GetVoIP](https://getvoip.com/predictive-dialer-software/)
- [Predictive Dialer Software for Outbound — Convoso](https://www.convoso.com/predictive-dialer/)
- [Predictive Dialer Explained — RingCentral](https://www.ringcentral.com/predictive-dialer.html)
- [TCPA Compliant Predictive Dialer — Platform28](https://www.platform28.com/predictive-dialer)
- [Best Predictive Dialer — Voiso](https://voiso.com/articles/best-predictive-dialer/)
- [Sales Sling TCPA Compliance](https://www.salessling.com/features/TCPA/tcpa-compliance)
- [Predictive Dialer Top 5 Picks 2026 — Nextiva](https://www.nextiva.com/blog/predictive-dialer-software.html)
