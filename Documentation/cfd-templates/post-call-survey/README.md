# 3CX CFD Post-Call Survey — Deployment Runbook

> **Public guide (SEO):** [https://connect.zentryc.com/kb/3cx-post-call-survey/](https://connect.zentryc.com/kb/3cx-post-call-survey/)

This guide connects the **3CX Call Flow Designer (CFD) Survey component** to the Zentryc portal ingest API.

**Prerequisites**

- 3CX **Call Flow Apps** / Call Flow Designer license (Enterprise)
- Tenant has **Survey Settings** enabled in the portal (`survey_enabled` + `survey_cfd_verified`)
- Portal reachable from the 3CX PBX host (HTTPS)

## 1. Portal setup

1. Log in as **company admin** → **Settings** → **Survey Settings**
2. Enable both feature flags and save
3. Create/save the **Post-Call CSAT** campaign with questions tagged: `solved`, `rating`, `comments`
4. Copy the **Ingest URL** and **X-Survey-Token** from the settings page

Or via management command (Smasco pilot, company id=2):

```bash
cd /home/ubuntu/3CX/cdr
python manage.py seed_survey_demo --company-id=2
```

## 2. CFD project (Call Flow Designer on Windows)

Reference: [3CX CFD Survey component](https://www.3cx.com/docs/cfd-survey-component/)

### Step A — Survey component

1. File → New → Callflow Project → name `ZentrycPostCallSurvey`
2. Drag **Survey** component → rename `CustomerFeedback`
3. Configure questions (tags must match portal):

| Order | Type | Tag | Prompt |
|-------|------|-----|--------|
| 1 | Yes/No | `solved` | Have we resolved the issue? Press 1 for yes, 2 for no. |
| 2 | Range 1–5 | `rating` | Rate the attention received, 1 to 5. |
| 3 | Recording | `comments` | Leave a comment; press # when finished. |

4. Add output field: name `caller`, value `session.ani`

### Step B — Parse Result (optional if using HTTP with variables)

If using the Survey `Result` CSV string, add **Execute C# Code** blocks per [3CX docs](https://www.3cx.com/docs/cfd-survey-component/) to split values.

### Step C — HTTP POST to portal

Add **Web Service REST** or **HTTP Request** component after the survey:

- **Method:** POST
- **URL:** `https://connect.zentryc.com/api/v1/survey-responses/ingest/`
- **Headers:**
  - `Content-Type: application/json`
  - `X-Survey-Token: <token from portal>`
- **Body** (Expression Editor):

```json
{
  "campaign_slug": "post-call-csat",
  "caller": "{{session.ani}}",
  "agent_dn": "{{session.variable.agent_dn}}",
  "queue_dn": "{{session.variable.queue_dn}}",
  "answers": [
    {"tag": "solved", "value": "{{GetSolvedResponse.ReturnValue}}"},
    {"tag": "rating", "value": "{{GetRatingResponse.ReturnValue}}"},
    {"tag": "comments", "value": "{{GetRecordingResponse.ReturnValue}}"}
  ]
}
```

Pass `agent_dn` / `queue_dn` from the queue disconnect script when possible — improves call linking.

### Step D — Build & deploy

1. Build → Build All → `ZentrycPostCallSurvey.zip`
2. 3CX Management Console → **Advanced** → **Call Flow Apps** → Add/Update
3. Assign a DID / extension to the app

## 3. Trigger survey after agent call

| Pattern | Configuration |
|---------|----------------|
| **Queue disconnect** | Queue → After call → Transfer to survey CFD DID |
| **IVR opt-in** | IVR menu option routes to survey DID |

## 4. Verify (E2E)

1. Place a test call through the queue; complete the survey
2. Portal → **Survey Dashboard** — response within ~2 seconds
3. Check **match confidence** on response detail (heuristic or exact)
4. Optional: `curl` test:

```bash
curl -X POST 'https://connect.zentryc.com/api/v1/survey-responses/ingest/' \
  -H 'Content-Type: application/json' \
  -H 'X-Survey-Token: YOUR_TOKEN' \
  -d '{"campaign_slug":"post-call-csat","caller":"966501234567","answers":[{"tag":"rating","value":"5"}]}'
```

## 5. Troubleshooting

| Issue | Fix |
|-------|-----|
| 403 on ingest | Enable survey flags + `license_verified` on campaign |
| Unmatched responses | Pass `agent_dn`/`queue_dn`; widen `match_window_minutes` |
| Duplicate responses | Idempotent — safe to retry; same caller+time returns 200 |
| No sidebar menu | Both `survey_enabled` and `survey_cfd_verified` must be true |

## Files in this folder

- `README.md` — this runbook
- `sample-payload.json` — example ingest body for CFD expressions
