# Phase 1 — Progress Log

## Session 1 — 2026-05-12

### Completed (6 tasks, all audited PASS)

| Task | Outcome | Audit |
|---|---|---|
| **P1-001** Hygiene cleanup | `.gitignore` added; `git rm --cached` removed venv/, __pycache__/, *.pyc, *.log, staticfiles/ | Tracked files **17,909 → 4,038 (-77.4%)**; on-disk files preserved |
| **P1-011 / P1-013** Vendor-neutral CDR | Added `source_pbx`, `external_id`, `correlation_id`, `raw_data`, `mos`, `jitter_ms`, `packet_loss_pct`, `latency_ms`, `codec` to `CallRecord`. New `cdr3cx/adapters/` package with `NormalizedCdr` dataclass + `PbxAdapter` ABC + `AdapterRegistry`. Migration `0014_callrecord_vendor_neutral` | **1,421,357 existing rows backfilled** to `source_pbx='3cx'`; 11 PBX vendors enumerated |
| **P1-015 / P1-016** Multi-currency | New `Currency` model (code, name, symbol, decimals); FK on `Company` + `country_code` + `vat_number`. Migration `accounts/0012_currency_and_company_locale` seeds 13 currencies (SAR/AED/EGP/QAR/KWD/BHD/OMR/JOD/USD/EUR/GBP/PKR/INR) and backfills all companies to SAR | 13 currencies seeded; both existing companies (Smasco, SAMNAN) defaulted to SAR |
| **P1-020** Tax engine | New `billing` app with `TaxRule` model. Migration `billing/0002_seed_tax_rules_and_default_fraud_rules` seeds 12 country rules: KSA 15%, UAE 5%, Egypt 14%, Qatar 5%, Bahrain 10%, Oman 5%, Kuwait 0%, Jordan 16%, UK 20%, US 0%, Pakistan 18%, India 18% | `TaxRule.calculate(Decimal('1000'))` for KSA returns 150.00 ✅ |
| **P1-057 → P1-061** Fraud rule engine (models) | `FraudRule` + `FraudIncident` models. 9 default rules seeded per company in shadow-mode (intl spike, after-hours intl, long intl, velocity calls/cost/duration, concurrent, new destination, premium destinations) | 18 rules total across 2 companies; all in shadow mode (safe rollout) |
| **P1-018** Currency template tag | `cdr3cx/templatetags/money_tags.py` — `{{ amount\|money:company.currency }}` filter + `{% tenant_currency %}` simple tag. Locale-aware decimal precision; RTL-safe non-breaking space; supports Currency object or ISO code string | All edge cases tested: SAR, KWD (3-decimal), USD, AED, EGP-by-code, empty, garbage input |

### Final state verification

```
✅ python manage.py check     → "System check identified no issues (0 silenced)"
✅ python manage.py showmigrations → all green, no unapplied
✅ Smoke test    → 1.42M CallRecords, 13 Currencies, 12 TaxRules, 18 FraudRules
```

### Files changed

- **New code:**
  - `.gitignore` (root)
  - `cdr/cdr3cx/adapters/__init__.py`
  - `cdr/cdr3cx/adapters/base.py` (NormalizedCdr + PbxAdapter ABC + AdapterRegistry)
  - `cdr/billing/` (new Django app)
  - `cdr/cdr3cx/templatetags/money_tags.py`

- **Modified:**
  - `cdr/cdr3cx/models.py` (CallRecord vendor-neutral fields)
  - `cdr/accounts/models.py` (Currency model + Company locale fields)
  - `cdr/cdr/settings.py` (registered `billing` app)

- **Migrations created:**
  - `cdr/cdr3cx/migrations/0014_callrecord_vendor_neutral.py`
  - `cdr/accounts/migrations/0012_currency_and_company_locale.py`
  - `cdr/billing/migrations/0001_initial.py`
  - `cdr/billing/migrations/0002_seed_tax_rules_and_default_fraud_rules.py`

### Cleanup notes

- Stale migration history from a previous, removed `billing` app was cleared from `django_migrations`; orphaned tables `billing_callrate` and `billing_userquota` were dropped.

---

---

## Session 2 — 2026-05-12

### Completed (5 tasks, all audited PASS)

| Task | Outcome | Audit |
|---|---|---|
| **P1-049** Install DRF + drf-spectacular | DRF 3.15.2 + drf-spectacular 0.27.2; REST_FRAMEWORK + SPECTACULAR_SETTINGS configured | `manage.py check` clean |
| **P1-050** API key model + auth | New `api` Django app with `ApiKey` model (SHA-256 hashed storage, `key_prefix` for identification, tier-aware, scopes JSON, expiry, revocation). `ApiKeyAuthentication` accepts `Authorization: Bearer <key>` or `X-API-Key`. `_ApiKeyUser` proxy exposes `.company` so existing tenant-scoping works | 18 tests pass; live curl with key returns 200; revoked key → 401 |
| **P1-051** Per-key rate limiting | `ApiKeyScopedThrottle` reads tier from `request.auth.tier` and resolves rate from `DEFAULT_THROTTLE_RATES['api_key.<tier>']`. Defensive: returns True if tier rate not configured | Throttle test: free-tier (2/min) → 3rd request returns 429 |
| **P1-052** REST endpoints | 12 viewsets registered: `currencies`, `companies`, `extensions`, `call-records` (with `since`/`until`/`source_pbx` filters), `call-patterns`, `quotas`, `user-quotas`, `tax-rules`, `fraud-rules`, `fraud-incidents` (+ `acknowledge` / `resolve` actions), `api-keys` (create returns plaintext once), `webhook-subscriptions` (+ `rotate_secret`). All tenant-scoped via `_TenantScopedMixin`. OpenAPI schema at `/api/schema/`, Swagger UI at `/api/docs/`, ReDoc at `/api/redoc/` | Live `/api/v1/call-records/` returned `count=256002` for tenant; tax-rules returned 12 (KSA + 11 others); cross-tenant isolation verified |
| **P1-053/054** Webhook subscriptions + delivery | `WebhookSubscription` (per-tenant URL + event list + HMAC secret) + `WebhookDelivery` (audit log + retry). `services/webhooks.py` handles fan-out, signing (`X-IPTPortal-Signature: sha256=…`), exponential backoff (0s / 1m / 10m / 1h, max 4 attempts). Signal handlers in `signals.py` auto-emit `call.completed` on `CallRecord` save and `fraud.detected` on `FraudIncident` save | 7 webhook tests pass: HMAC determinism, success → delivered, 500 → retry scheduled, retries-exhausted → failed, event-not-subscribed → skipped, signal fan-out works for both events |

### Bugs caught & fixed during audit

- **TaxRule queryset bug:** `qs.filter(company__in=[None, company.pk])` returns 0 rows because Django doesn't translate `None` in `__in` to `IS NULL`. Fixed to `Q(company__isnull=True) | Q(company=company)`. Caught by live curl returning `count=0` when 12 rules exist.
- **Throttle init crash:** DRF instantiates throttle classes before request handling, calling `get_rate()` without a scope. Fixed by deferring rate lookup to `allow_request()` and reading live api_settings each call.

### Test summary
```
Ran 18 tests in 0.806s — OK (auth, schema, tenant isolation, webhooks, throttling)
```

### Live endpoints proven
| URL | Auth | Result |
|---|---|---|
| `GET /api/v1/health/` | none | `{"status":"ok"}` |
| `GET /api/v1/extensions/` | none | `401` |
| `GET /api/v1/extensions/` | Bearer/X-API-Key | `200` |
| `GET /api/v1/currencies/` | API key | 13 currencies |
| `GET /api/v1/call-records/` | API key | `count=256002` (tenant-scoped) |
| `GET /api/v1/fraud-rules/` | API key | 9 default rules |
| `GET /api/v1/tax-rules/` | API key | 12 country rules |
| `GET /api/docs/` | none | Swagger UI HTML |
| `GET /api/schema/` | none | OpenAPI 3.0.3 YAML |

---

---

## Session 3 — 2026-05-12

### Completed (5 tasks, all audited PASS)

| Task | Outcome | Audit |
|---|---|---|
| **P1-060** Country resolver | `billing/services/country.py` — `iso_country()` resolves ISO 3166-1 alpha-2 from caller/callee using `phonenumbers`; treats short numbers as internal | 4 tests cover E.164, local Saudi, internal extension, empty |
| **P1-059** Fraud rule evaluator | `billing/services/fraud.py` — 10 rule-type evaluators (intl_spike, after_hours_intl, premium_destination, blacklist_country, velocity_calls/cost/duration, new_destination, long_intl, concurrent_calls). `evaluate_call()` walks active rules per company, creates `FraudIncident` rows, executes configured action (alert / disable_extension / block_route). `billing/signals.py` wires `post_save` on `CallRecord` | Live audit on SAMNAN: synthetic call to +995501234567 (Georgia) for 180s correctly triggered both `long_intl` (alert mode) and `new_destination` (shadow mode) — exactly as designed |
| **P1-061** Auto-disable extension | `_execute_action()` toggles `Extension.disable_external_call=True` when rule action=`disable_extension` and `shadow_mode=False` | Test: critical rule disables extension; same rule in shadow mode does NOT |
| **P1-062** Incident dashboard | `billing/views.py` + `billing/urls.py` + `templates/billing/fraud_incident_dashboard.html`. Sidebar entry under Billing menu. KPI tiles (open / critical / high / last 24h), status + severity filters, per-row acknowledge/resolve/false-positive actions, shadow-mode banner | Django test client: page renders, synthetic incident appears, acknowledge/resolve update status correctly, cross-tenant user CANNOT see other tenant's incidents |
| **P1-063** Free toll-fraud audit (lead-gen) | `billing/services/audit_report.py` — parses CSV (column-tolerant), runs 4 audit rules (premium destinations / after-hours intl / long intl / extension velocity), renders branded PDF via ReportLab. Public route `/billing/free-fraud-audit/` accepts file upload + contact info, returns PDF directly. No CDR data persisted | Live curl: GET form 200; POST with CSRF + sample CSV → 4,638-byte PDF starting with `%PDF-1.4` magic |

### Test summary
```
Ran 40 tests in 1.911s — OK (api: 18, billing: 22)
```

### Endpoint inventory after Session 3
| URL | Auth | Purpose |
|---|---|---|
| `GET /billing/fraud-incidents/` | login | Internal incident dashboard with KPI + filters |
| `POST /billing/fraud-incidents/<id>/acknowledge/` | login | Mark incident acknowledged |
| `POST /billing/fraud-incidents/<id>/resolve/` | login | Mark incident resolved |
| `POST /billing/fraud-incidents/<id>/false-positive/` | login | Mark incident as false positive |
| `GET /billing/free-fraud-audit/` | public | Lead-gen landing page |
| `POST /billing/free-fraud-audit/` | public | CSV upload → PDF audit |

### Bug caught & fixed during audit
- `velocity_cost` test failed because `CallRecord.save()` runs `categorize_call()` which overwrites `call_rate` from the company's `CallPattern` table. Test now seeds a `CallPattern` with the desired rate so the cost computation is deterministic.

### What this completes
The fraud line is now end-to-end: rules seeded per tenant on signup → auto-evaluated on every CDR → incidents shown in dashboard with action buttons → optional auto-disable of extensions → webhook fan-out to external systems → public lead-gen tool that converts cold prospects via PDF report. Ready to charge SAR 199–499/mo as add-on per the pricing strategy doc.

---

---

## Session 4 — 2026-05-12

### Completed (5 tasks, all audited PASS)

| Task | Outcome | Audit |
|---|---|---|
| **P1-043** Channels + ASGI | `channels[daphne] 4.1`, daphne added to INSTALLED_APPS (first), `cdr/asgi.py` rewritten as `ProtocolTypeRouter` (HTTP→Django, WS→AuthMiddleware→URLRouter), `CHANNEL_LAYERS` set to `InMemoryChannelLayer` (Redis-ready comment included) | `python manage.py runserver` now serves via Daphne ASGI; "Listening on TCP address 127.0.0.1:18099" |
| **P1-044** WS consumer | New `realtime` app: `consumers.WallboardConsumer` joins `wallboard.company.<id>` group on connect, sends initial snapshot, supports client-initiated `refresh`, returns 4401/4403 close codes for unauth/no-company | `WebsocketCommunicator` test: anonymous connection rejected, authenticated connect receives snapshot frame with `counters`, ws round-trip works |
| **P1-045** Event publishing | `realtime/signals.py` post_save handlers on `CallRecord` + `FraudIncident` use `async_to_sync(layer.group_send)` to push `call.completed` and `fraud.detected` events to per-company group | Unit test `test_call_save_pushes_live_event` confirms: save CDR → consumer receives `call.completed` with caller in payload |
| **P1-046/P1-047** Wallboard frontend | `templates/realtime/wallboard.html` (8 KPI tiles, hourly Chart.js bar, recent-calls ticker, toast container for fraud alerts, auto-reconnecting WS, status badge). `wallboard_projection.html` (full-screen dark theme for TV mode). Sidebar entries added under Dashboards menu | Live curl: GET wallboard 200 (54k bytes, `/ws/wallboard/` wired), projection 200 (7.5k, dark theme), heatmap 200 (77k) |
| **P1-048** Heatmap | `realtime/snapshot.build_heatmap()` returns 7×24 grid; `templates/realtime/heatmap.html` renders color-intensity cells (Tailwind blue scale), falls back to grey for zero-volume slots; `/realtime/wallboard/heatmap.json` JSON endpoint for AJAX refresh | Test confirms 7×24 shape; live page 200; JSON endpoint returns valid grid |

### Live network audit (real Daphne server + WS round-trip)
```
✓ Daphne ASGI listening on 127.0.0.1:18099
✓ WS handshake successful via real network connection
✓ Initial frame type=snapshot
✓ Counter keys: ['answer_rate','answered','avg_duration','in_progress','missed','total','total_cost','total_duration']
✓ Recent: 10 entries, hourly: 24 buckets
✓ Refresh round-trip works (snapshot reflects 698 total / 635 answered for SAMNAN)
```

### Known limitation (documented for production)
The default `InMemoryChannelLayer` is single-process. If a CDR is created by a Celery worker, socket-server process, or different Django process, the live event won't fan-out across processes. **Production must switch to** `channels_redis.core.RedisChannelLayer` (one-line settings change — comment included in `cdr/settings.py`). The in-process round-trip is fully proven by 11 passing unit tests including `test_call_save_pushes_live_event`.

### Bugs caught & fixed during audit
1. **Snapshot tests failed** because test CallRecords had `call_time=NULL` (no model default) and snapshot filters by `call_time__gte=window_start`. Fixed by passing `call_time=timezone.now()` explicitly.
2. **WebSocket consumer tests crashed with `psycopg2.InterfaceError: connection already closed`** — Django's `TestCase` wraps each test in a transaction that conflicts with `database_sync_to_async`. Fixed by switching `WallboardConsumerTests` to `TransactionTestCase`.
3. **`additional_headers` keyword broken in audit script** because installed `websockets==13.1` uses `extra_headers`. Audit script updated.

### Test summary
```
Ran 51 tests in 8.650s — OK (api: 18, billing: 22, realtime: 11)
```

### Endpoint inventory after Session 4
| URL | Auth | Purpose |
|---|---|---|
| `WS  /ws/wallboard/` | session | Per-company live KPI feed |
| `GET /realtime/wallboard/` | login | Live wallboard with KPIs + Chart.js + recent-calls ticker |
| `GET /realtime/wallboard/projection/` | login | Full-screen dark TV mode |
| `GET /realtime/wallboard/heatmap/` | login | 7×24 call-volume heatmap |
| `GET /realtime/wallboard/heatmap.json` | login | JSON for AJAX refresh |

### Cumulative phase-1 score
- Sessions 1–4 complete: 21 of 73 tasks (29%)
- Tests: 51 passing
- Tracked file count stable at 4,038
- New revenue lines now demo-able: **fraud product + real-time wallboard**

---

---

## Session 5 — 2026-05-12

### Completed (4 tasks, all audited PASS)

> **2FA (P1-068) intentionally deferred** at user request — to be picked up later.

| Task | Outcome | Audit |
|---|---|---|
| **P1-069** Audit log + middleware | New `security` Django app with `AuditLogEntry` model + 3 middleware classes: `AuditLogMiddleware` writes one row per state-changing request (POST/PUT/PATCH/DELETE) capturing user, email, method, path, status, IP, user-agent. `signals.py` also captures `user_logged_in` for LOGIN_SUCCESS audit trail. Append-only admin (no edit/delete). Browsable dashboard at `/security/audit-log/` with user/method/path/status filters | Live: synthetic POST recorded both the request itself + login → entries went 0 → 2; dashboard renders rows with badges; tenant-isolated |
| **P1-070** Per-tenant IP whitelist | `CompanyIpWhitelist` (CIDR list) + `IpWhitelistMiddleware`. Honors `CompanySecurityPolicy.enforce_ip_whitelist` flag; supports `X-Forwarded-For` for behind-proxy deployment. Blocks generate audit entries with `object_repr=IP_WHITELIST_BLOCK` | Live: IP `10.0.0.1` → 403; IP `198.51.100.42` (in `198.51.100.0/24` whitelist) → 200 |
| **P1-071** API key scope enforcement | New `HasApiKeyScope` DRF permission class — `view.required_scopes` checked against `ApiKey.scopes`. Empty scopes list grants all (back-compat). Sample wired on `CallRecordViewSet` (`read:cdr`), `ExtensionViewSet` (`read:extensions`), `FraudIncidentViewSet` (`read:fraud`) | Live: key with `['read:fraud']` → `/fraud-incidents/` 200, `/call-records/` 403 |
| **P1-072/P1-073** Password policy + session timeout | `StrongPasswordValidator` (min 12 chars, upper+lower+digit+symbol). `PasswordHistoryValidator` (no reuse of last 5; auto-snapshots on save via pre_save signal). Per-tenant `CompanySecurityPolicy.session_timeout_minutes` applied by `DynamicSessionTimeoutMiddleware` on every authenticated request | Live: `'weak'` → 4 reasons rejected, `'NoSymbol12345'` → 1 reason rejected, `'Strong-Pass-1234!'` → accepted; tenant policy 15-min timeout reflected in session expire_date |

### Test summary
```
Ran 69 tests in 19.445s — OK (api: 18, billing: 22, realtime: 11, security: 18)
```

### Bug caught & fixed during audit
- Audit-log dashboard template used `{{ "..."|split:"," }}` — Django doesn't ship a `split` filter. Fixed by inlining the option list explicitly.

### Endpoint inventory after Session 5
| URL | Auth | Purpose |
|---|---|---|
| `GET /security/audit-log/` | login | Browsable per-tenant audit log with filters |
| (admin) `/admin/security/auditlogentry/` | superuser | Read-only (append-only) audit detail |
| (admin) `/admin/security/companyipwhitelist/` | admin | Manage per-tenant CIDR whitelist |
| (admin) `/admin/security/companysecuritypolicy/` | admin | Per-tenant security policy |

### Cumulative phase-1 score
- Sessions 1–5 complete: **25 of ~73 tasks (34%)**
- Tests: **69 passing** (was 51)
- Tracked file count: 4,038
- Compliance posture massively improved: append-only audit log + per-tenant IP whitelist + strong password validators + reuse prevention + per-tenant session timeout — major checkboxes for SOC 2 / SAMA / NCA RFPs

---

## What's next (Phase 1 still pending)

From `tasks/phase1-tasks.md`, ~67 of 73 tasks remain. Highest-priority next batch:

| Group | Tasks |
|---|---|
| **Public API + auth** | P1-049 → P1-056 (DRF, OpenAPI, API keys, webhooks) |
| **Real-time wallboard** | P1-043 → P1-048 (Channels, WebSocket, frontend tiles) |
| **Invoicing + payments** | P1-024 → P1-037 (Invoice model, PDF, Stripe/HyperPay/PayTabs/Tap, dunning) |
| **Fraud — runtime** | P1-059 (real-time evaluator), P1-062 (incident dashboard), P1-063 (free audit) |
| **Arabic RTL** | P1-038 → P1-042 (i18n, RTL CSS, AR translations, bilingual PDF) |
| **DevOps** | P1-002 (CI), P1-003 (staging), P1-004 (Gunicorn+Nginx hardening), P1-005 (Sentry), P1-009 (Redis), P1-010 (Celery+Beat) |
| **Security baseline** | P1-068 → P1-073 (2FA, audit log, password policy) |
| **Notifications** | P1-064 → P1-067 (channel adapters, scheduled email reports) |

Recommended next session: pick one of these groups end-to-end.
