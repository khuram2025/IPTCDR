# Security & Compliance

This document is the security and compliance baseline for the connect.zentryc.com 3CX platform — a multi-tenant Django 5.0.7 monolith (`/home/ubuntu/3CX/cdr`) that ingests, rates and reports on **1,492,192 call records** across two live Saudi tenants (Smasco, SAMNAN). It audits production hardening, tenant isolation, RBAC, audit logging and data protection, then ranks remediation by severity and effort. It assumes the topology, ingestion and roadmap detail described in [02-Current-System-Architecture-Audit.md](02-Current-System-Architecture-Audit.md), [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md) and [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md), and does not repeat them.

## TL;DR / Key Takeaways

- **The application is configured for development, not production.** `DEBUG = True`, `ALLOWED_HOSTS = ['*']`, a `django-insecure-` `SECRET_KEY`, and **database credentials hardcoded in source** all ship live (`cdr/settings.py:22-33,285-286`). Any one of these is a Critical finding on its own; together they are a full-stack disclosure and trust-boundary failure.
- **An unauthenticated raw-TCP CDR socket is bound to `0.0.0.0` and exposed to the public internet.** `socket_server.py:144` binds every tenant's `listening_port` (8000/8005) with no authentication, no source-IP allowlist and no framing. `records.txt` (4,928 lines) is full of internet scanner / `androxgh0st` probes hitting it. This is the platform's single largest external attack surface.
- **No TLS terminates in the deployed nginx config.** `/etc/nginx/sites-enabled/cdr` listens on `:80` only for all hostnames; the app *trusts* `X-Forwarded-Proto` (`SECURE_PROXY_SSL_HEADER`) but nothing in the shown config guarantees HTTPS, so portal credentials and session cookies for KSA tenants can traverse plaintext.
- **Tenant isolation is convention-based, not enforced.** Every view manually appends `.filter(company=request.user.company)` (16 sites in `views.py` alone). There is no row-level security, no tenant-scoped manager, and no test harness — one forgotten filter leaks one tenant's calls to another.
- **The `security` app is a genuine, well-built head start** — per-tenant IP allowlist, audit log, password history/policy and dynamic session timeout already exist (`security/models.py`, `security/middleware.py`) and the public API stores only **SHA-256 hashes** of API keys (`api/models.py`). The gap is *coverage and activation*, not absence.
- **Compliance posture for KSA is currently non-conformant.** Tenants are `Asia/Riyadh`; CDRs contain real subscriber MSISDNs (e.g. `to_no = 00966554778081`) which are **personal data** under Saudi PDPL and GDPR. There is no retention policy, no documented lawful basis, no DPA/RoPA, and no call-recording consent model (recordings are out of scope today but on the roadmap). Plaintext transport + `DEBUG` traceback disclosure would themselves be reportable.

---

## 1. Production Hardening Checklist

The most severe issues are misconfigurations, not missing features. Each is a one-to-few-line fix with outsized risk reduction.

| # | Finding | Evidence (`path:line`) | Risk | Sev | Effort |
|---|---------|------------------------|------|-----|--------|
| H1 | `DEBUG = True` in production | `cdr/settings.py:25` | Stack traces leak settings, SQL, file paths, env on any 500; Django serves verbose error pages to anyone | Critical | S |
| H2 | `ALLOWED_HOSTS` contains `'*'` | `cdr/settings.py:27-33` | Host-header injection, cache poisoning, password-reset link poisoning; defeats the explicit host list above it | Critical | S |
| H3 | Hardcoded `django-insecure-` `SECRET_KEY` in VCS | `cdr/settings.py:22` | Forge session cookies, signed tokens, password-reset tokens; full account takeover. Key is also in git history | Critical | S |
| H4 | DB credentials in source (`USER='read'`, `PASSWORD='Read@123'`) | `cdr/settings.py:285-286` | Credentials in repo + this doc set; rotate and externalize. (Mitigated only by the account being read-only) | Critical | S |
| H5 | Unauthenticated CDR socket on `0.0.0.0`, internet-exposed | `socket_server.py:144`; probes in `records.txt` | Anyone can inject forged CDRs (skew billing/quota), DoS the per-connection thread pool, or fingerprint the host | Critical | M |
| H6 | No TLS in deployed nginx; plaintext `:80` only | `/etc/nginx/sites-enabled/cdr:13,54` | Credential/session-cookie interception; no HSTS; KSA tenants on plaintext | Critical | M |
| H7 | No secure-cookie / HSTS / clickjacking flags | absent in `cdr/settings.py` | Session cookie sent over HTTP; framing/XSS hardening missing | High | S |
| H8 | Commented-but-present SMTP password in source | `cdr/settings.py:312` | Stale secret in VCS; rotate | Medium | S |

### Target configuration

Drive all of the above from environment variables and fail closed:

```python
# cdr/settings.py — target
import os
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]            # H3: no default; crash if unset
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"   # H1: default off
ALLOWED_HOSTS = os.environ["DJANGO_ALLOWED_HOSTS"].split(",")  # H2: explicit, no '*'

DATABASES["default"]["USER"] = os.environ["DB_USER"]    # H4
DATABASES["default"]["PASSWORD"] = os.environ["DB_PASSWORD"]

# H6/H7 — only when TLS terminates at nginx:
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
```

`python manage.py check --deploy` should be wired into CI and must pass before release; it flags H1–H3 and H7 automatically. Secrets should move to environment files managed outside the repo (or a secrets manager), and **H3/H4/H8 require key/credential rotation**, not just relocation, because the values are already committed.

### The CDR socket (H5) — defense in depth

The socket is the strategic ingestion liability called out in [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md). Until ingestion moves to the recommended outbound, authenticated **read-only DB pull** from each 3CX `cdr_output` table, the existing socket must be contained:

1. **Bind to a private interface / firewall the port.** The PBX reaches us over a fixed route; `0.0.0.0` exposure to the world is unnecessary. Restrict at the host firewall / security group to the known PBX source IP per tenant.
2. **Source-IP allowlist in `handle_client()`** — reject `client_sock.getpeername()[0]` if it is not the configured PBX address for that `listening_port`. This is the same allowlist primitive the `security` app already implements for the web tier (`security/middleware.py:71`).
3. **Move the long-record fix and validation here too** — the `recv(1024)` hard read (`socket_server.py:31`) both truncates legitimate records and means malformed/oversized scanner payloads are silently parsed; bound and validate input explicitly.

These are tactical mitigations. The durable fix is to stop accepting *inbound* connections from the internet for CDR at all (see [03](03-CDR-Ingestion-and-3CX-Integration.md) and the phased plan in [12](12-Migration-Plan-and-Phased-Roadmap.md)).

---

## 2. Tenant Isolation Review

Two tenants share one database, one Redis, one app process and one set of tables, distinguished only by `Company` (`accounts/models.py:47`) and resolved at ingest by `listening_port`. Isolation today is **enforced by developer discipline**, which does not scale to the multi-vendor, multi-call-center future the stakeholder wants.

| Aspect | Current state | Risk | Target |
|--------|---------------|------|--------|
| Query scoping | Manual `.filter(company=request.user.company)` repeated ~16× in `views.py` (also `quota_views.py`, `callpattern_views.py`, `api/views.py`) | One missing filter = cross-tenant data leak; impossible to audit by reading every view | Tenant-scoped default manager + base queryset; deny-by-default |
| Object access | Detail/edit views fetch by PK; relies on the same manual filter | IDOR — guessing a CallRecord/Extension PK from another tenant | `get_object_or_404(scoped_qs, pk=...)` everywhere; never the unscoped default manager |
| Ingest routing | `Company.objects.get(listening_port=port)` (`socket_server.py:24`) | Two tenants sharing a port, or a forged record on an open socket (H5), mis-attributes calls/billing | Authenticated per-tenant connector + signed source identity |
| Realtime / cache | Channels groups + Redis cache shared | Group-name collisions could fan a wallboard event to the wrong tenant | Namespace every Channels group and cache key with `company_id` (see [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md)) |
| Background isolation | n/a (no Celery/cron running) | When async lands, jobs must carry tenant context | Tenant id mandatory on every task/event |

**Recommendation — make the safe path the default path.** Introduce a `TenantScopedManager` and a thin mixin so views cannot accidentally touch the global table:

```python
class TenantScopedManager(models.Manager):
    def for_company(self, company):
        return self.get_queryset().filter(company=company)

class CompanyScopedViewMixin:
    """Every view returns only the requesting user's tenant rows."""
    def get_queryset(self):
        return super().get_queryset().filter(company=self.request.user.company)
```

For hard, defense-in-depth isolation, evaluate **PostgreSQL Row-Level Security** (a `company_id` policy keyed off a per-connection `SET app.current_company`) so the database refuses cross-tenant reads even if application code is wrong. Pair this with a **cross-tenant isolation test** (seed two companies, assert tenant A's session can never retrieve tenant B's `CallRecord`/`Extension`/`UserQuota`) added to CI — there is no such test today. Schema-level isolation options interact with the indexing/partitioning work in [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md) and should be decided jointly.

---

## 3. RBAC Review

There are **two parallel authorization systems** and they are not reconciled:

- A coarse string `role` on `CustomUser` with choices `superadmin` / `company_admin` / `user` and helper predicates `is_superadmin()` etc. (`accounts/models.py:104,117-123`).
- A richer custom-`Role` model with Django `Permission` M2M and a `UserRole` junction (`accounts/models.py:156-194`) — clearly intended for fine-grained, per-company roles, but views overwhelmingly branch on the simple `role` string.

| Finding | Evidence | Sev | Effort |
|---------|----------|-----|--------|
| Two RBAC models, one (custom `Role`/`UserRole`) largely unused by views | `accounts/models.py:156-194` vs `role` checks in views | High | M |
| Authorization is checked ad hoc per view, not centrally | scattered `request.user.role` / `is_superadmin` branches | High | M |
| `superadmin` is effectively global across tenants | `create_superuser` sets `is_staff`/`is_superuser` + `role='superadmin'` (`accounts/models.py:85-93`) | Medium | S |
| Django admin reachable; no documented MFA for privileged users | `django.contrib.admin` enabled (`settings.py:51`) | High | M |
| No call-center role hierarchy (agent / supervisor / manager) | absent | High | L |

**Recommendations.**
1. **Converge on one model.** Make the custom `Role`/`UserRole` + Django `Permission` the single source of truth; reduce the `role` string to a convenience label or derive it. Define a fixed permission catalog (view reports, manage quotas, manage patterns, manage billing, admin users, view recordings, monitor live calls).
2. **Centralize enforcement** via DRF permission classes and Django `PermissionRequiredMixin`/`@permission_required`, not per-view `if` branches, so authorization is auditable in one place.
3. **Introduce the call-center role hierarchy** the priority San Francisco tenant needs — **Agent → Supervisor → Manager** — with supervisor visibility scoped to assigned teams/queues. This is a hard dependency of [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md) (monitor/whisper/barge, agent-vs-supervisor dashboards) and must be vendor-neutral for the Cisco CUCM expansion ([10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md)).
4. **Protect privileged access**: require MFA for `superadmin`/`company_admin` and for `/admin/`, restrict `/admin/` by IP (reuse the allowlist), and log all privileged actions to the audit trail.

---

## 4. Audit Logging Coverage

The `security` app implements a clean audit primitive: `AuditLogMiddleware` writes one `AuditLogEntry` per state-changing HTTP request, capturing `company`, `user`, `user_email` snapshot, `method`, `path`, `status_code`, `ip`, `user_agent` and a JSON `extra` (`security/models.py:19-51`, `security/middleware.py:36`). This is a strong foundation — it is correctly tenant-stamped and indexed on `(company, -created_at)`.

| Gap | Detail | Sev | Effort |
|-----|--------|-----|--------|
| HTTP-only scope | Captures POST/PUT/PATCH/DELETE web requests; misses **logins/logouts, failed logins, lockouts, password changes, API-key use, and the socket ingest path** | High | M |
| No security-event semantics | Records *path*, not *meaning* — "who exported all CDRs", "who viewed a recording", "auth failed 12×" are not distinguishable | High | M |
| No tamper-evidence / retention floor | Same DB, deletable by an app-level superadmin; no hash-chaining or WORM/export | Medium | M |
| Sensitive read events not logged | Bulk CDR export and (future) recording playback are the highest-value PII actions and are unlogged | High | M |

**Recommendations.** Emit explicit security events alongside the request log — `auth.login`, `auth.login_failed`, `auth.locked_out`, `password.changed`, `apikey.used`, `data.exported`, `recording.played`, `tenant.config_changed` — via Django auth signals and the API auth layer. Log the **outcome of the IP-allowlist block** (already partially done at `security/middleware.py:102-104`) and **CDR-socket connection accept/reject** decisions. For compliance, set a **minimum retention** for the audit log distinct from CDR retention, make it append-only (revoke `DELETE`/`UPDATE` from the app DB role on the audit table, or ship to an external WORM/SIEM sink), and consider per-entry hash-chaining for tamper-evidence. Audit-log delivery and alert routing tie into [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md).

---

## 5. Data Protection, PII & Compliance

### 5.1 What personal data the platform holds

CDRs are **personal data**. Live rows contain real subscriber MSISDNs and extension identities — e.g. `from_no = Ext.5322`, `to_no = 00966554778081` — across all **1,492,192** records, plus `from_dispname`/`to_dispname`/`final_dispname` display names and `caller`/`callee` numbers. The roadmap adds **call recordings**, which are the most sensitive category (voice biometrics, conversation content). Notably, the vendor-neutral `raw_data` JSONB column is **0% populated today** (`COUNT(raw_data)=0`); once the DB-pull connector starts storing untouched vendor payloads there, it will become a concentrated PII store and must be in scope from day one.

### 5.2 Applicable frameworks (Asia/Riyadh tenants)

| Framework | Why it applies | Headline obligations engaged here |
|-----------|----------------|-----------------------------------|
| **Saudi PDPL** (PDPL + Implementing Regs, SDAIA) | `TIME_ZONE = Asia/Riyadh`; Smasco/SAMNAN are KSA entities processing KSA personal data | Lawful basis, data-subject rights, breach notification to SDAIA, data-residency/transfer controls, retention limits, RoPA |
| **CITC** telecom rules | Call-accounting over Saudi telephony numbers | Sector data-handling/retention expectations; consent for monitoring/recording |
| **SAMA** Cyber Security Framework | *If/when* financial-sector tenants are onboarded | Mandated controls (encryption, logging, access control, BCP); raises the bar above PDPL alone |
| **GDPR** | Multi-tenant SaaS roadmap likely touches EU contacts/operators | Same control families as PDPL; useful as the strict baseline |

The platform currently satisfies **none** of these at a documented-control level: plaintext transport (H6) and `DEBUG` traceback disclosure (H1) would themselves be reportable security failings, and there is no lawful-basis record, retention schedule, RoPA or breach-response runbook.

### 5.3 Findings and recommendations

| Finding | Risk | Sev | Effort | Target |
|---------|------|-----|--------|--------|
| No data-retention policy; 22 months (2024-07 → 2026-06) of CDRs kept indefinitely | PDPL/GDPR storage-limitation breach; ever-growing PII liability | High | M | Per-tenant retention policy (e.g. 12–24 mo CDR, shorter for recordings) with automated purge/anonymization |
| No PII minimization/masking in UI/exports | Over-exposure of MSISDNs to non-privileged users and in exports | Medium | M | Mask numbers by role; gate full numbers + exports behind a permission and audit each access |
| Call-recording **consent** unmodeled (recordings on roadmap) | Recording without consent violates PDPL/CITC/GDPR | High | L | Per-tenant/per-queue consent config + announcement; store consent basis with each recording; encrypt at rest; strict access + audit |
| `raw_data` will hold untouched vendor PII | Unbounded, unclassified PII store | Medium | M | Classify, encrypt, retention-tag, and minimize raw payloads at ingest |
| No subject-rights workflow (access/erasure) | Cannot service PDPL/GDPR data-subject requests | Medium | M | Tenant-scoped lookup + export/erase tooling keyed on number/extension |
| No data-residency guarantee documented | KSA residency expectations under PDPL/CITC | Medium | M | Document hosting region; keep KSA tenant data in-region; control cross-border transfer |
| Quota alerts misdeliver PII to a developer | `send_quota_alert()` hardcodes `recipient='khuram2025@gmail.com'` (`cdr3cx/models.py:371`) — tenant usage data leaks to one external address; the live `superuser` runs as this same address | High | S | Route to the extension/tenant owner; remove the hardcoded address |

The **quota-alert leak is both a privacy defect and a notifications bug** — every tenant's quota/usage email goes to a single developer mailbox instead of the data owner. Fix it here for the privacy impact and track the delivery redesign in [06-Billing-Quota-and-Fraud.md](06-Billing-Quota-and-Fraud.md) and [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md).

---

## 6. Prioritized Remediation Roadmap

Sequenced so the highest-risk, lowest-effort production-hardening items land first (a single coordinated config/secrets release), followed by structural isolation/RBAC work, then compliance program build-out. This maps onto the phases in [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md).

| Priority | Item | Sev | Effort | Phase |
|----------|------|-----|--------|-------|
| P0 | Set `DEBUG=False`; remove `'*'` from `ALLOWED_HOSTS`; externalize + **rotate** `SECRET_KEY` and DB/SMTP creds (H1–H4,H8) | Critical | S | Immediate |
| P0 | Terminate TLS at nginx (HTTPS/443, redirect 80→443, HSTS) + secure-cookie flags (H6,H7) | Critical | M | Immediate |
| P0 | Firewall the CDR socket to known PBX IPs; add source-IP allowlist in `handle_client()` (H5) | Critical | M | Immediate |
| P0 | Remove hardcoded `khuram2025@gmail.com` quota-alert recipient | High | S | Immediate |
| P1 | Tenant-scoped manager/mixin + cross-tenant isolation test in CI | High | M | Near-term |
| P1 | Wire `manage.py check --deploy` into CI as a release gate | High | S | Near-term |
| P1 | Expand audit log to auth/API/export/recording events; make append-only | High | M | Near-term |
| P1 | MFA + IP-restriction for `superadmin`/`company_admin` and `/admin/` | High | M | Near-term |
| P2 | Converge on single `Role`/`Permission` RBAC; central enforcement | High | M | Mid-term |
| P2 | Agent/Supervisor/Manager role hierarchy (vendor-neutral) | High | L | Mid-term (with [05](05-Call-Center-Evaluation-Module.md)) |
| P2 | Data-retention policy + automated purge/anonymization | High | M | Mid-term |
| P2 | PostgreSQL Row-Level Security on `company_id` | Medium | L | Mid-term (with [04](04-Data-Model-and-Database-Performance.md)) |
| P3 | Call-recording consent model + encryption-at-rest + access audit | High | L | With recordings ([05](05-Call-Center-Evaluation-Module.md)) |
| P3 | PDPL/GDPR program: RoPA, DPA, lawful basis, subject-rights tooling, breach runbook, residency | High | XL | Program |

### Closing assessment

The platform is **one focused hardening sprint away** from removing every Critical production-config and exposure finding (P0), because the worst issues are misconfigurations, not architectural defects — and the `security` app already supplies the allowlist, audit, password-policy and session-timeout building blocks the rest of the plan extends. The structural work (enforced tenant isolation, unified RBAC, the call-center role hierarchy) is where security converges with the product roadmap, and the compliance program (PDPL/GDPR/CITC/SAMA) should be stood up in parallel before recordings and additional tenants materially increase the personal-data footprint. Treat P0 as a release blocker.

---

*Related: [02-Current-System-Architecture-Audit.md](02-Current-System-Architecture-Audit.md) · [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md) · [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md) · [05-Call-Center-Evaluation-Module.md](05-Call-Center-Evaluation-Module.md) · [06-Billing-Quota-and-Fraud.md](06-Billing-Quota-and-Fraud.md) · [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md) · [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md) · [11-Gap-Analysis-and-Feature-Backlog.md](11-Gap-Analysis-and-Feature-Backlog.md) · [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md)*
