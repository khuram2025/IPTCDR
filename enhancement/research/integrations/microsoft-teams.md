# Integration — Microsoft Teams (Phone)

## Overview
Microsoft Teams Phone is the fastest-growing UC platform. Call records are exposed via the **Microsoft Graph API** under the `microsoft.graph.callRecords` namespace. Records are created **after a call/meeting ends** and retained for **30 days**.

## Architecture
```
[ Customer's M365 tenant ] ──Graph API──> [ Our adapter service ]
                                                   │
                                                   ├─ webhook (push) for new callRecord events
                                                   └─ delta query (pull) as fallback
                                                   │
                                                   ▼
                                          [ NormalizedCdr → Kafka ]
```

## Setup steps for customer
1. Azure AD admin clicks "Connect Teams" in our portal → starts OAuth consent flow
2. Approves application with permission `CallRecords.Read.All`
3. We register webhook subscription against `/communications/callRecords`
4. Webhook delivery starts within minutes; backfill via delta pull for last 30 days

## Required permissions
- `CallRecords.Read.All` — application permission, admin consent required
- `User.Read.All` — for participant resolution
- (Optional) `CallRecord-PstnCalls.Read.All` for Direct Routing PSTN call details

## Key API endpoints we use
- `POST /subscriptions` — create webhook subscription
- `GET /communications/callRecords/{id}` — retrieve full record
- `GET /communications/callRecords/{id}/sessions` — get sessions for a record
- `GET /communications/callRecords/getDirectRoutingCalls(...)` — Direct Routing PSTN calls
- `GET /communications/callRecords/getPstnCalls(...)` — PSTN calls

## Webhook payload (push model)
- Notification with `subscriptionId`, `resourceData.id` (callRecord ID)
- We then fetch the full record via Get callRecord
- Renew subscription before 3-day expiry

## Pull / delta-query fallback
- Run every 15 min: list new call records with `$filter=startDateTime ge {lastSync}`
- Stores cursor per tenant; resilient to webhook failures

## NormalizedCdr field mapping
| Teams field | NormalizedCdr field |
|---|---|
| callRecord.id | external_id |
| callRecord.startDateTime | call_time |
| callRecord.endDateTime | end_time |
| callRecord.lastModifiedDateTime | updated_at |
| participants_v2[*] | parties (caller + callee resolved by UPN) |
| callRecord.organizer_v2.userPrincipalName | organizer_email |
| callRecord.type | call_type (peerToPeer / group / unknown) |
| sessions[].caller / sessions[].callee | per-leg details |
| sessions[].failureInfo | termination_reason |

For PSTN / Direct Routing calls:
| Field | Map to |
|---|---|
| pstnCallLogRow.calleeNumber / callerNumber | caller / callee (E.164) |
| duration | duration |
| chargeAmount, currency | (informational) |

## Auto Attendant + Call Queue analytics
- Available via Power BI template + REST API
- Endpoint: `/communications/getCallSummaries`, queue/auto-attendant historical reports
- We ingest these for IVR + queue metrics

## Adapter implementation notes
- Use `msgraph-sdk-python` or raw HTTPS
- Token caching with `msal` lib
- Webhook validation per Microsoft spec (validation token)
- Idempotency on `callRecord.id`
- Handle subscription renewal before expiry (cron job)

## Pain points
- **Admin consent** required for `CallRecords.Read.All` — we must explain why permission is needed
- **30-day retention** in Graph — we must ingest within window
- **Webhook lag** can be a few minutes — supplement with pull
- **Discretion warning** from Microsoft: this permission is sensitive; data protection requirements apply

## Customer-facing setup doc requirements
- Permission justification text for admin consent screen
- Step-by-step screenshots for Azure AD app registration
- Troubleshooting: subscription renewal failure, missing records

## Sources
- [Working with Call Records API — Microsoft Learn](https://learn.microsoft.com/en-us/graph/api/resources/callrecords-api-overview?view=graph-rest-1.0)
- [Call Records in Cloud Communications API](https://learn.microsoft.com/en-us/graph/cloud-communications-callrecords)
- [Microsoft Graph Call Records API FAQ](https://learn.microsoft.com/en-us/graph/callrecords-api-faq)
- [New Call Records API capabilities — Microsoft 365 Dev Blog](https://devblogs.microsoft.com/microsoft365dev/new-microsoft-graph-callrecords-api-capabilities/)
- [callRecord.getDirectRoutingCalls](https://learn.microsoft.com/en-us/graph/api/callrecords-callrecord-getdirectroutingcalls?view=graph-rest-1.0)
- [Get callRecord](https://learn.microsoft.com/en-us/graph/api/callrecords-callrecord-get?view=graph-rest-1.0)
- [Teams API Overview](https://learn.microsoft.com/en-us/graph/api/resources/teams-api-overview?view=graph-rest-1.0)
- [Auto attendant & Call queue historical reports](https://learn.microsoft.com/en-us/microsoftteams/aa-cq-historical-reports)
- [Set up Call Analytics for Teams](https://learn.microsoft.com/en-us/microsoftteams/set-up-call-analytics)
- [Get callRecording](https://learn.microsoft.com/en-us/graph/api/callrecording-get?view=graph-rest-1.0)
