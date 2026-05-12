# Vertical — AI Voice Agents (Conversational AI)

## Market opportunity
- Multilingual AI voice agents = hot category in 2026
- Top vendors: Robylon AI, Retell AI, Synthflow, Vapi, PolyAI, Google Dialogflow CX, Talkdesk, ElevenLabs Agents
- Pricing range: **$0.05 - $0.50 per minute**
- Enterprise + dedicated infra: **30-50% premium**
- Arabic + dialect support is **a real differentiator** in MENA

## Pricing benchmarks
| Vendor | Pricing |
|---|---|
| CloudTalk AI Voice Agent | $350/mo for 1,000 min, then $0.50/min |
| Ringg AI | $0.10/min (Flexible), $0.06/min (Enterprise) |
| Retell AI | starts $0; pay-as-you-use |
| Telnyx Conversational AI | usage-based |
| Soniox Arabic STT | ~$0.12/hour |
| Deepgram (multilingual) | competitive per-minute |

## What customers want
1. **Natural conversation** (sub-1-second turn latency)
2. **Multi-language** including Arabic dialects, English, Urdu, Hindi, Tagalog (common workforce languages in MENA)
3. **Code-mixed speech** (e.g., Gulf Arabic + English code-switching)
4. **Custom voice** matching brand
5. **Backend integration** (CRM, calendar, payment, ERP)
6. **Bot → human handoff** with context
7. **Compliance** (recording, redaction, opt-out)

## Use cases
- **Inbound IVR replacement** — "Press 1" trees → conversational
- **Outbound campaigns** — surveys, appointment confirmation, debt collection
- **FAQ deflection** — knowledge base Q&A bot
- **Appointment booking** — calendar integration
- **Lead qualification** — first-pass screening
- **After-hours support** — when humans unavailable

## IPT Voice Agent product (Phase 4)

### Architecture
```
[ Caller ]
    │
    ▼
[ Streaming STT ] ──> [ LLM dialog manager ] ──> [ Streaming TTS ] ──> [ Caller ]
    │                       │                          │
    │                       ├─ Tool calls (CRM, Calendar, KB, Payment)
    │                       └─ Bot → Human handoff (with transcript)
    │
    └─ Recording → transcription → analytics (sentiment, summary, QA)
```

### Stack choices
| Component | Recommended |
|---|---|
| Streaming STT (Arabic strong) | Soniox or Azure Speech (Saudi/Gulf dialect) |
| Streaming STT (English fallback) | Whisper (self-hosted) or Deepgram |
| LLM dialog manager | Claude / GPT-4 / Llama 3 fine-tuned |
| TTS (Arabic) | ElevenLabs multilingual or Azure Neural Voice |
| TTS (English) | ElevenLabs |
| Custom voice cloning | ElevenLabs voice cloning (premium) |
| Telephony | Twilio Programmable Voice OR direct SIP via 3CX/Zoom/Teams |

### Latency budget
- **Total turn latency target: <800ms** (caller stops → bot starts)
- STT: <250ms (streaming, partial transcripts)
- LLM: <300ms (small model + caching) or longer with bigger model
- TTS: <200ms (streaming start)
- Network + jitter: ~100-150ms

### Languages supported (target)
- **Arabic** — MSA + Saudi + Gulf + Egyptian + Levantine dialects
- **English**
- **Urdu** (large Pakistani workforce in MENA)
- **Hindi** (large Indian workforce)
- **Tagalog** (large Filipino workforce)
- **French** (North Africa)

### Pricing model
- **Per-minute billing** (matches industry)
- SAR 1.50/min (~$0.40) standard rate
- SAR 1.00/min (~$0.27) Enterprise
- + **Setup fee** for custom voice clone (SAR 5,000-15,000)
- + **Knowledge base ingestion** professional services

### Per-vertical use cases
- **Banking:** card block bot, balance inquiry (with strong auth), branch info
- **Healthcare:** appointment booking, lab results retrieval (with auth), prescription refill
- **Hospitality:** room service, concierge, check-out reminders
- **Government:** citizen survey, status updates, FAQ
- **Telco:** balance check, tariff info, complaint logging
- **Retail/E-commerce:** order status, returns, FAQ

## What to differentiate on
1. **Arabic dialect quality** — most global vendors are weak here
2. **Code-mixed speech handling** (English + Arabic)
3. **MENA telephony numbers + local DID** (out-of-box)
4. **Pre-built vertical templates** (banking, healthcare, govt)
5. **Integrated with our analytics + recording + billing** (not standalone)
6. **Compliance** (SAMA-compliant logging of bot conversations for banks)

## Sources
- [7 Multilingual Voice AI Agents 2026 — Robylon](https://www.robylon.ai/blog/7-best-multilingual-ai-voice-agents-2026)
- [Deepgram + IBM Voice Capabilities for Enterprise](https://newsroom.ibm.com/2026-02-24-deepgram-and-ibm-introduce-advanced-voice-capabilities-for-enterprise-ai)
- [How Much Does Voice AI Cost 2026 — CloudTalk](https://www.cloudtalk.io/blog/how-much-does-voice-ai-cost/)
- [10 Best Multilingual Chatbots and Voice Agents 2026 — Crescendo](https://www.crescendo.ai/blog/best-multilingual-chatbots)
- [AI Phone Agent Pricing — Retell AI](https://www.retellai.com/pricing)
- [Conversational AI Pricing — Telnyx](https://telnyx.com/pricing/conversational-ai)
- [Voice AI Pricing Top 7 Solutions 2026 — Crunch](https://thecrunch.io/voice-ai-pricing/)
- [Voice AI Development Costs 2026 — Master of Code](https://masterofcode.com/blog/voice-ai-development-costs)
- [10 Best Multilingual AI Voice Agents — Ringg](https://www.ringg.ai/blogs/best-multilingual-ai-voice-agents)
- [Best Arabic Speech-to-Text — Soniox](https://soniox.com/speech-to-text/use-cases/voice-agents/arabic)
- [State of AI Calling 2026 — Auto Interview AI](https://www.autointerviewai.com/blog/the-state-of-ai-calling-competitors-2026-latency-pricing-report)
- [9 Best Speech Analytics Software — AmplifAI](https://www.amplifai.com/blog/call-center-speech-analytics-software)
