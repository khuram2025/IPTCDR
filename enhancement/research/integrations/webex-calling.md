# Integration — Webex Calling

## Overview
Webex Calling exposes CDRs via the **Webex Detailed Call History API** with three modes:
- **CDR Stream endpoint** — recommended for continuous consumption
- **CDR Feed endpoint** — for historical reporting (5 min ago to 30 days back, 12-hour windows max per request)
- **Reports endpoint** (`/v1/reports`) — for windows >30 days

CDRs are available **48 hours after** the call to **5 minutes ago** (latency).

## Architecture
```
[ Customer's Webex org ] ──API + webhook──> [ Our adapter ]
                                                   │
                                                   ├─ CDR Stream (continuous)
                                                   ├─ CDR Feed (backfill)
                                                   └─ Detailed Call Records webhook (Partner Hub)
                                                   │
                                                   ▼
                                          [ NormalizedCdr → Kafka ]
```

## Setup steps for customer
1. Customer admin clicks "Connect Webex Calling" → starts OAuth flow
2. Authorize with required scopes:
   - `spark-admin:calling_cdr_read`
   - `spark-admin:locations_read`
   - `analytics:read_all` (for Reports API)
3. We start CDR Stream consumer + Webhook subscription
4. Backfill last 7 days via CDR Feed

## Endpoints
- **CDR Stream:** `https://analytics.webexapis.com/v1/cdr_feed` (continuous; cursor-based)
- **CDR Feed:** same URL but with `startTime` / `endTime` query params (12-hour windows)
- **Detailed Call History (Reports):** `/v1/reports` with `templateId=detailed-call-history`
- **Webhook:** Detailed Call Records webhook in Webex Partner Hub (push)

## Key field mappings
| Webex CDR field | NormalizedCdr field |
|---|---|
| Call ID / Correlation ID | external_id (use Correlation ID for multi-leg dedupe) |
| Call start time | call_time |
| Duration | duration |
| Calling number | caller |
| Called number | callee |
| Called line ID | callee_display_name |
| Direction | direction (inbound/outbound/internal) |
| Call type | call_type |
| Release reason | termination_reason |
| Site main number | location |
| User UUID / User ID | extension_id / user reference |
| Codec | codec |
| Network MOS / RTT / jitter | mos, latency, jitter |

## Adapter implementation notes
- For continuous: use CDR Stream endpoint with checkpointed cursor
- For backfill / gap recovery: use CDR Feed with 12-hour windows iterated
- Webhook for real-time push (Partner Hub config)
- Use Correlation ID to merge multi-leg calls
- Token refresh via OAuth refresh token

## Pain points
- **Latency:** CDR not available for ~5-30 min after call end
- **12-hour window limit** on Feed endpoint requires iteration for backfill
- **Reports endpoint** for >30-day historical data

## Sources
- [Webex Detailed Call History API blog](https://developer.webex.com/blog/webex-detailed-call-history-api)
- [Understanding Webex Calling CDR APIs](https://developer.webex.com/blog/understanding-the-webex-calling-cdr-apis)
- [Exploring Webex Calling Reports & Analytics APIs](https://developer.webex.com/blog/exploring-the-webex-calling-reports-and-analytics-apis)
- [Reports: Detailed Call History reference](https://developer.webex.com/docs/api/v1/reports-detailed-call-history)
- [Detailed Call Records webhook in Partner Hub](https://help.webex.com/en-us/article/n5zr85e/Detailed-Call-Records-webhook-for-Webex-Calling-in-Partner-Hub)
- [Calling APIs Overview](https://developer.webex.com/blog/calling-apis-overview)
- [Get Detailed Call History endpoint](https://developer.webex.com/docs/api/v1/reports-detailed-call-history/get-detailed-call-history)
- [Webex Calling Data & CDRs guide — Metropolis](https://www.metropolis.com/articles/whats-in-cisco-webex-calling-data.php)
