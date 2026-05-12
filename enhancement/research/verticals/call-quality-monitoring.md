# Vertical — VoIP Call Quality Monitoring

## What & why
- Customers complain about "bad calls" but troubleshooting is hard without data
- **MOS (Mean Opinion Score)**, **jitter**, **packet loss**, **latency** are industry-standard metrics
- Adding these to our reports + dashboards becomes a powerful differentiator
- Helps customers **pick best carrier** + **negotiate SLAs**

## Key metrics

### MOS (Mean Opinion Score)
- Subjective measurement, scale 1.0-5.0
- 4.5 = highest with G.711 codec
- ≥3.5 = acceptable
- <3.0 = poor

### Latency (one-way)
- <150ms = good
- 150-300ms = acceptable
- >300ms = poor (echo, talk-over)

### Jitter (packet arrival variance)
- <30ms = good
- 30-100ms = noticeable
- >100ms = poor

### Packet loss
- <1% = acceptable
- 1-2.5% = noticeable
- >2.5% = poor

## Where data comes from per PBX
| PBX | Source |
|---|---|
| Cisco CUCM | CMR (Call Management Records) — paired with CDR |
| Webex Calling | CDR includes Network MOS, RTT, jitter |
| Microsoft Teams | Call Quality Dashboard (CQD) + sub-stream stats |
| Zoom Phone | QoS data in call logs |
| 3CX | exports per-call quality metrics |
| Asterisk | RTCP reports if enabled |
| Generic SIP | requires SBC-side capture (RTP/RTCP via VoIPmonitor) |

## What to build (Phase 3)

### Data ingestion
- Capture quality fields from every adapter
- Store in CallRecord (mos, jitter, packet_loss, latency, codec)
- Roll up to ClickHouse for analytics

### Dashboards
- **Per-call quality** (drill into bad calls)
- **Per-route / per-carrier comparison** (which carrier delivers best quality?)
- **Per-extension / per-location** (where are the bad calls happening?)
- **Per-codec analysis**
- **Trend over time** (degradation alerts)

### Alerts
- "Carrier X had >5% packet loss in last 10 min" → SMS to admin
- "Extension Y consistently low MOS" → tech ticket
- "Jitter spike on SIP trunk" → ops ticket

### Reports
- Monthly quality scorecard per carrier
- SLA compliance report (if customer has SLA with carrier)

## Reference vendors
- **VoIPmonitor** (open source, mature, ~$300/server license for commercial)
- **SolarWinds VNQM**
- **NetBeez**
- **WhatsUp Gold** (VoIP monitor module)
- **Catchpoint** (synthetic + RTP analysis)
- **OneUptime** (modern, IPv6-aware)

## Differentiation
- Most call accounting platforms **don't include quality** — competitors stop at CDR
- Variphy has it for Cisco/UCCX; Tollring has limited; Imagicle doesn't lead on it
- Our angle: **quality alongside cost + carrier comparison** is unique value

## Pricing
- Bundle with **IPT Insight Pro** tier
- Add-on for SBC-level real-time RTP monitoring (Phase 4): **+SAR 999/mo**

## Sources
- [VoIPmonitor SIP/RTP Monitoring & Recording](https://www.voipmonitor.org/)
- [VoIPmonitor Call Quality Monitoring Feature](https://www.voipmonitor.org/feature/quality)
- [Impact of Packet Loss, Jitter, Latency — NetBeez](https://netbeez.net/blog/impact-of-packet-loss-jitter-and-latency-on-voip/)
- [Open-Source VoIP Quality Monitoring — ICT Innovations](https://www.ictinnovations.com/utilizing-open-source-tools-for-voip-quality-monitoring-and-troubleshooting)
- [How to Monitor VoIP Quality over IPv6 — OneUptime](https://oneuptime.com/blog/post/2026-03-20-monitor-voip-quality-ipv6/view)
- [8 Best Jitter Tools for VoIP Quality Testing 2026 — ITPRC](https://www.itprc.com/best-jitter-tools/)
- [SolarWinds VoIP Network Quality Manager](https://www.solarwinds.com/voip-network-quality-manager/use-cases/call-quality)
- [VoIP Jitter Survival Guide — Obkio](https://obkio.com/blog/voip-jitter/)
- [Measuring VoIP Quality with SIP and RTP — Catchpoint](https://www.catchpoint.com/blog/voip-sip-rtp)
- [WhatsUp Gold VoIP Monitor](https://www.whatsupgold.com/resources/data-sheets/voip-monitor)
