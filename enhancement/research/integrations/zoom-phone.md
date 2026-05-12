# Integration — Zoom Phone

## Overview
Zoom Phone exposes CDR + call logs via REST API + real-time webhooks. Multi-leg calls share a `call_uuid` for reconstruction.

## Architecture
```
[ Customer's Zoom account ] ──REST + webhooks──> [ Our adapter ]
                                                       │
                                                       ├─ Scheduled REST pull (every 5-15 min)
                                                       └─ Webhook for real-time events
                                                       │
                                                       ▼
                                              [ NormalizedCdr → Kafka ]
```

## Setup steps for customer
1. Install our app from the Zoom Marketplace
2. OAuth consent with scopes:
   - `phone:read`
   - `phone:read:admin`
   - `phone_call_log:read:admin`
   - `phone_recording:read:admin` (if recording ingestion enabled)
3. We start scheduled call-log fetch + webhook subscription

## Endpoints
- **Call logs:** `GET /phone/call_logs` (paginated, supports `from`/`to` filters)
- **Real-time data:** webhook subscription via Zoom Developer Console
- **Recordings:** `GET /phone/recordings`

## Webhook events of interest
- `phone.callee_answered`
- `phone.callee_ended`
- `phone.recording_completed`
- `phone.voicemail_received`
- `phone.emergency_alert`
- (newer) `phone.call_summary` — AI summary

## Key field mappings
| Zoom field | NormalizedCdr field |
|---|---|
| call_id | external_id |
| call_uuid | correlation_id (for multi-leg dedupe) |
| direction | direction |
| caller_number | caller |
| callee_number | callee |
| caller_name / callee_name | display names |
| date_time | call_time |
| duration | duration |
| call_type | call_type |
| call_result | termination_reason |
| call_path[] | sessions / call legs |
| recording.url + recording.id | recording reference |

## Multi-leg reconstruction
- Cloud-native logs require session normalization using `call_uuid`
- A transferred call may produce 2-3 legs sharing call_uuid → join into one logical record

## Adapter implementation notes
- Scheduled pull via cron / serverless function — incremental with checkpointing
- Webhook handler with HMAC signature verification
- Idempotency on `call_id`
- Recording download (if subscribed) → S3 storage → transcription pipeline
- Pagination handling (`next_page_token`)

## Use as reseller
- Zoom has a Phone reseller program
- Our billing platform can compute charges per minute from CDR + LCR
- Useful for MSPs who resell Zoom Phone

## Pain points
- Webhook reliability (retries needed)
- Rate limits on REST API (~30 req/sec by default)
- Recording downloads can be large; manage storage carefully
- Some fields are admin-only and require admin OAuth

## Sources
- [Integrate with Zoom Phone — Developer Docs](https://developers.zoom.us/docs/phone/integrate-with-zoom-phone/)
- [Get Real-Time Call Data — Zoom](https://developers.zoom.us/docs/phone/call-data/)
- [Using webhooks — Zoom](https://developers.zoom.us/docs/api/webhooks/)
- [Automated Zoom Phone Call Record Export — Devforum](https://devforum.zoom.us/t/automated-zoom-phone-call-record-export/39942)
- [AI Call Summary Webhook — Devforum](https://devforum.zoom.us/t/ai-call-summary-webhook/131807)
- [Integrate Engagement Data — Zoom Tech Library](https://library.zoom.com/business-services/zoom-contact-center/expert-insights/integrate-engagement-data)
- [Zoom Phone Call Logs Explained — Metropolis](https://www.metropolis.com/articles/zoom-phone-call-logs-explained.php)
- [Call Monitor via API — Devforum](https://devforum.zoom.us/t/call-monitor-via-api/86591)
