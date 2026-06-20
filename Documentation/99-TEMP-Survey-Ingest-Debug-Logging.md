# 99 — TEMP: Survey Ingest Debug Logging & Cloudflare Real-IP

> **Purpose of this file:** It documents the *temporary* instrumentation added on
> **2026-06-15** to debug the 3CX Call Flow Designer (CFD) survey ingest endpoint.
> When debugging is finished and you want to remove the verbose per-request logging,
> **follow the "How to remove" section** — it lists every file and the exact change to revert.

Endpoint under observation: `https://connect.zentryc.com/api/v1/survey-responses/ingest/`

---

## What was added (2 independent pieces)

### Piece A — Cloudflare real-IP restoration  *(recommended to KEEP)*
Makes nginx (and the app) see the **real visitor IP** instead of a Cloudflare edge IP.
This is generally desirable in production — only remove if you specifically want to revert.

- **File created:** `/etc/nginx/conf.d/cloudflare-realip.conf`
  - Contains Cloudflare's IPv4/IPv6 ranges via `set_real_ip_from …`
  - `real_ip_header CF-Connecting-IP;`
  - `real_ip_recursive on;`
- Applied in nginx **http** context (conf.d is included globally), so it affects all vhosts.

### Piece B — Per-request ingest logging  *(the TEMP part — remove when done)*
Writes a dedicated line for **every** hit to the ingest endpoint (any HTTP method),
capturing the **real IP, user-agent, masked token, full request body, and response body**.

- **Log file produced:** `/home/ubuntu/3CX/logs/survey_ingest.log` (+ rotated `.1` … `.5`)
- **Isolated logger** (`propagate=False`) → nothing else writes to that file.

Files touched for Piece B:

| # | File | Change |
|---|------|--------|
| 1 | `cdr/cdr/settings.py` | In `LOGGING`: added formatter `ingest`, handler `survey_ingest_file`, logger `survey_ingest` |
| 2 | `cdr/api/views.py` | Added `import json` / `import logging`; helpers `_ingest_logger`, `_ingest_client_ip()`, `_mask_token()`; and `SurveyIngestView.finalize_response()` |

> ⚠️ **Do NOT confuse this with the permanent feature work.** The survey **question/answer-option
> CRUD** feature (model `SurveyQuestionOption`, migration `surveys/0002_*`, the editor views/templates)
> is a *permanent* feature — **keep it**. Only Pieces A/B above are operational/temporary.

---

## Exact code that was added (for reference when reverting)

### settings.py — `LOGGING`
Added formatter:
```python
'ingest': {
    'format': '{asctime} {message}',
    'style': '{',
},
```
Added handler:
```python
# Dedicated log: ONLY survey-response ingest API hits (request + response).
'survey_ingest_file': {
    'level': 'INFO',
    'class': 'logging.handlers.RotatingFileHandler',
    'filename': '/home/ubuntu/3CX/logs/survey_ingest.log',
    'maxBytes': 1024 * 1024 * 5,  # 5 MB
    'backupCount': 5,
    'formatter': 'ingest',
    'delay': True,  # open file on first write (handler runs as the gunicorn user)
},
```
Added logger:
```python
# Isolated logger — writes ONLY to survey_ingest.log, nothing else.
'survey_ingest': {
    'handlers': ['survey_ingest_file'],
    'level': 'INFO',
    'propagate': False,
},
```

### api/views.py
- Top of file: `import json` and `import logging`
- Above `class SurveyIngestView`: module-level `_ingest_logger`, `_ingest_client_ip()`, `_mask_token()`
- Inside `class SurveyIngestView`: the `finalize_response(self, request, response, *args, **kwargs)` method that calls `_ingest_logger.info(...)`

---

## How to remove (revert the TEMP logging — Piece B)

### Option 1 — git (cleanest, if these went in as a commit)
```bash
cd /home/ubuntu/3CX/cdr
git log --oneline -- cdr/settings.py api/views.py   # find the commit
git revert <commit>        # or manually undo the blocks below
```

### Option 2 — manual edit
1. **`cdr/api/views.py`**
   - Delete the `finalize_response(...)` method from `SurveyIngestView`.
   - Delete the module-level `_ingest_logger`, `_ingest_client_ip()`, `_mask_token()` helpers.
   - Remove `import json` and `import logging` **only if** nothing else in the file uses them.
2. **`cdr/cdr/settings.py`** → in `LOGGING`, remove the three blocks added above
   (`ingest` formatter, `survey_ingest_file` handler, `survey_ingest` logger).
3. **Delete the log files**
   ```bash
   rm -f /home/ubuntu/3CX/logs/survey_ingest.log /home/ubuntu/3CX/logs/survey_ingest.log.*
   ```
4. **Restart the app**
   ```bash
   sudo systemctl restart gunicorn.service
   ```
5. **Verify** no errors:
   ```bash
   cd /home/ubuntu/3CX/cdr && .venv/bin/python manage.py check
   ```

## How to remove Piece A (Cloudflare real-IP) — only if you really want to
```bash
sudo rm /etc/nginx/conf.d/cloudflare-realip.conf
sudo nginx -t && sudo systemctl reload nginx
```
After this, nginx logs and the app will again see Cloudflare edge IPs instead of real visitor IPs.

---

## Watching the log while debugging
```bash
sudo tail -f /home/ubuntu/3CX/logs/survey_ingest.log
```
Each hit looks like:
```
2026-06-15 07:39:29,045 HIT POST ip=2a02:4780:41:7df9::1 ua='curl/8.5.0' token=wMqd…BIts
  REQUEST : {"campaign_slug": "post-call-csat", "caller": "+966512345678", ... }
  RESPONSE 201: {"id": 16, "created": true, "match_confidence": "unmatched", ...}
```
**Spotting a *real* 3CX post:** it will show the PBX's **real public IP** (not a Cloudflare
`172.x` / `162.x` address, now that Piece A is active) and a **non-`curl` user-agent**.

---

## Other operational notes from this session (not logging-related)
- `/home/ubuntu/3CX/cdr/debug.log` was `chmod 666` so management commands could run as user `net`
  (it is owned by `ubuntu`). To restore stricter perms: `sudo chmod 664 /home/ubuntu/3CX/cdr/debug.log`.
- `/tmp/devsettings.py` is a throwaway local override (redirects log paths to `/tmp`) used only for
  running `manage.py check`/`test` as user `net`. It is **not** part of the deployment and can be ignored/deleted.
- Token used in examples is SAPTCO's campaign ingest token; treat tokens as secrets.

_Last updated: 2026-06-15_
