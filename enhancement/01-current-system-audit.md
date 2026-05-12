# Current System Audit

**Source repo:** `/home/ubuntu/3CX/cdr/`
**Live URL:** https://iptportal.channab.com/dashboard/ (login required)
**Stack:** Django 4.x, Python 3.12, custom user/auth, signal-driven cost engine

---

## 1. Django apps installed

| App | Purpose |
|---|---|
| `cdr3cx` | Core CDR ingestion, dashboards, billing logic, call-center module |
| `accounts` | CustomUser, Company, Role, UserRole, OTP password reset, SMTP settings |
| `notifications` | Notification scaffolding |
| `import_export` | CSV/Excel import (used for Extension model in admin) |
| `crispy_forms` + `crispy_bootstrap4` | Form rendering |
| `mathfilters` | Template math (recently added) |

---

## 2. URL routes (all under `/`)

### Core CDR / dashboard
- `/dashboard/` — main analytics dashboard
- `/all_calls/`, `/incoming/`, `/outgoing/`, `/outgoing_international/`, `/summary/`

### Call-center module (just shipped)
- `/call-center/` — IVR + agent dashboard
- `/call-center/agent/<extension>/` — per-agent detail
- `/call-center/missed-calls/` — missed-call analysis
- `/call-center/call-back-tracking/` — callback follow-up

### Reporting
- `/top-extensions/` (+ `/excel-report/`, `/pdf/`)
- `/sales-reports/` — pre-filtered list of sales extensions
- `/caller-calls/<caller_number>/` (+ `?export_excel=true`, `?export_pdf=true`)
- `/country-specific-calls/<country_slug>/`

### Billing / quotas
- `/quotas/` (+ `/create/`, `/<id>/update/`, `/<id>/delete/`, `/assign/`, `/usage/`)
- `/extension/<id>/add-balance/`

### Call patterns (rate cards)
- `/callpatterns/` (+ CRUD)

### 3CX integration
- `/get-3cx-version/`, `/get_users/`, `/get-user-groups/<user_id>/`

### CDR ingestion
- `/cdr` — POST endpoint for socket-server forwarded records
- `/update-call-stats/` — AJAX refresh

---

## 3. Database models (entities tracked)

### Calls
**`CallRecord`** — full CDR row
- caller, callee, call_time, duration, country
- call_category (mobile/national/intl/local/unknown)
- call_rate, total_cost
- from_type, to_type, final_type (Extension / Ivr / Script / VMail / Queue / etc.)
- from_dispname, to_dispname, final_dispname (display names — agent attribution)
- termination_reason, queue info
- FK to Company and Extension

### Billing
- **`CallPattern`** — regex/prefix → call_type → rate_per_min (SAR)
- **`Quota`** — frequency (daily/weekly/monthly) + amount
- **`UserQuota`** — total / used / remaining per extension
  - auto-resets per frequency
  - signal handler on `CallRecord.save` triggers `UserQuota.deduct_balance()`
  - 90% threshold triggers email alert
  - on overage, can auto-toggle `Extension.disable_external_call`

### Org / users
- **`CustomUser`** — email-primary, role field (superadmin/company_admin/user)
- **`Company`** — multi-tenant separation, has `listening_port` (per-company 3CX socket port)
- **`Extension`** — extension number, full_name, email, `disable_external_call` toggle
  - on save, auto-creates `UserQuota`
- **`Role`** — per-company custom roles with permission map
- **`UserRole`** — junction
- **`PasswordResetOTP`** — 6-digit, 10-min validity
- **`SMTPSettings`** — instance-wide SMTP config (with test-email view)

---

## 4. Templates (UI screens)

70+ templates under `cdr/templates/`:

- **Dashboards:** `cdr/dashboard.html`, `cdr/call_record_summary.html`
- **Call lists:** `all_calls.html`, `outgoingExtCalls.html`, `incomingCalls.html`, `outgoingInternationalCalls.html`
- **Reports:** `top_extensions.html`, `country_specific_calls.html`, sales reports
- **Call center (new):** `cdr/callcenter/dashboard.html`, `agent_details.html`, `missed_calls.html`, `call_back_tracking.html`
- **Billing:** `cdr/quota/*.html`, call-pattern CRUD
- **Auth:** login, OTP reset, SMTP settings
- **Navigation:** `partials/sidebar.html` — role-aware menu (Dashboards / Billing / Call Center / Sales Calls / Settings)
- **Public:** `landing/index.html` (just added)

---

## 5. Integration surface

### What works
- **3CX socket server** — listens on per-company `listening_port`, parses 20-field CSV format
- **3CX REST API** — get version, list users, get user groups (OAuth2)
- **HTTP push endpoint** `/cdr` — alternative to socket
- **Extension import** — Django admin CSV import via `import_export`

### What's missing
- No Cisco CUCM adapter (FTP/SFTP CDR pull)
- No MS Teams adapter (Graph API call records)
- No Webex Calling adapter (Detailed Call History API)
- No Zoom Phone adapter (REST API + webhooks)
- No generic SIP/Asterisk/FreePBX adapter
- No public REST API (consumers can only push to `/cdr`)
- No webhooks (out-bound notifications)
- No CRM integrations (Salesforce/HubSpot/Zoho/Bitrix24)

---

## 6. Multi-tenancy posture

### Strengths
- All queries filter by `request.user.company`
- `CompanyValidationMiddleware` enforces company context
- Per-company 3CX socket port → automatic data routing
- Custom roles per company (not just global roles)

### Weaknesses
- No tenant data residency selection (KSA-only deployment)
- No tenant-scoped feature flags / module enable-disable
- No per-tenant rate-limiting / SLA tier
- No tenant impersonation for support (superadmin can switch companies but no audit trail of "viewing as")

---

## 7. Reporting & exports

| Report | Filter | Export |
|---|---|---|
| Dashboard analytics | Date / call type | — |
| Top extensions | Sort by count/duration/cost | Excel + PDF |
| Sales reports | Hard-coded extension list | — |
| Country-specific | Country slug | — |
| Caller history | Per extension | Excel + PDF |
| Outgoing international | — | Excel + PDF |
| Quota usage | Per company | — |

**Gap:** no scheduled reports (daily/weekly email), no custom report builder, no report sharing/permissions, no KPI definitions library.

---

## 8. Security & compliance posture

| Area | Status |
|---|---|
| Authentication | ✅ Email + bcrypt, OTP reset |
| Authorization | ✅ Role-based + custom permissions |
| Audit log | ❌ None |
| 2FA / MFA | ❌ Only OTP for password reset, not login |
| API keys | ❌ N/A (no API) |
| Rate limiting | ❌ None |
| Data encryption at rest | ❌ Not documented |
| SOC 2 / ISO 27001 | ❌ Not started |
| GDPR right-to-erasure | ❌ No workflow |
| PCI redaction | ❌ N/A (no recordings) |
| Backup / DR | ❌ Not documented |

---

## 9. Code-base hygiene issues

These should be cleaned up immediately:

- `cdr/venv/` is committed to git (137k lines added in last commit alone)
- `cdr/__pycache__/*.pyc` and `cdr3cx/__pycache__/*.pyc` are committed
- `cdr/debug.log`, `debug.log.1`, `debug.log.2` are tracked
- `cdr/staticfiles/` is committed (should be build artifact)
- Recent commit messages are very short ("Before Samnan Change") — hard to audit history

**Action:** create `.gitignore` covering `venv/`, `__pycache__/`, `*.pyc`, `*.log`, `staticfiles/`, then `git rm --cached -r` those paths.

---

## 10. Strengths to defend

| Strength | Why it matters |
|---|---|
| Per-extension quota with auto-disable on overage | Most competitors don't do this — it's a real product feature |
| Per-company port-based 3CX routing | Clean multi-tenant ingestion design |
| Custom per-company roles | Already enterprise-grade RBAC |
| Real-time CDR ingestion (not batch) | Better than CSV-poll competitors |
| Excel + PDF exports baked in | Saudi customers expect this |
| MENA presence + Arabic team | Cultural moat global vendors can't match |

---

## 11. Weaknesses to fix (ordered by impact)

1. **Single PBX support (3CX only)** — biggest blocker to growth
2. **No invoicing or payment gateway** — limits to "internal chargeback," not true SaaS
3. **No call recording / transcription / sentiment** — locks out 2026 RFPs
4. **No real-time wallboards** — lost demos to Variphy / Tollring
5. **No public REST API** — can't integrate, can't be a "platform"
6. **No fraud detection** — both a liability and a missed revenue line
7. **No Arabic UI / multi-currency** — caps MENA expansion
8. **No CRM integrations** — sales-team buyers walk away
9. **No mobile app** — supervisors expect this in 2026
10. **No SOC 2 / ISO 27001** — enterprise procurement gate

These are addressed in `02-gap-analysis.md` with severity scoring and in `07-roadmap.md` with sequencing.
