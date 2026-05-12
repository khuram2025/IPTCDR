# Phase 1 — Granular Task List (Months 0-3)

Each task has: ID, title, acceptance criteria, effort (XS=1-3d, S=1w, M=2-4w), and dependencies.

---

## EPIC: Hygiene & DevOps

### P1-001 — Add `.gitignore` and remove tracked artifacts
- **AC:** `venv/`, `__pycache__/`, `*.pyc`, `*.log`, `staticfiles/`, `.env`, `db.sqlite3` ignored. `git rm --cached -r` applied. Repo size ↓80%+
- **Effort:** XS
- **Dep:** none

### P1-002 — Set up GitHub Actions CI pipeline
- **AC:** PR opens → flake8/black + pytest run; status check required to merge
- **Effort:** S
- **Dep:** P1-001

### P1-003 — Create staging environment
- **AC:** Separate AWS account / VPC; same Docker image as prod; smaller instance sizes; auto-deploy from `main` branch
- **Effort:** S

### P1-004 — Replace Django dev server with Gunicorn + Nginx in prod
- **AC:** Gunicorn workers tuned to CPU; Nginx serves static; HTTPS via Let's Encrypt or ACM
- **Effort:** S

### P1-005 — Add Sentry error tracking
- **AC:** Backend + frontend exceptions captured; per-tenant tag; alerting on new error types
- **Effort:** XS

### P1-006 — Add structured JSON logging
- **AC:** All logs in JSON; `request_id`, `tenant_id`, `user_id` in every log line; `python-json-logger` or `structlog`
- **Effort:** XS

### P1-007 — Add health and readiness endpoints
- **AC:** `/healthz` (always 200) and `/readyz` (200 only when DB+Redis reachable)
- **Effort:** XS

### P1-008 — Set up automated test scaffolding
- **AC:** `pytest-django` configured; factory-boy fixtures for User, Company, Extension, CallRecord; CI runs full suite in <3 min
- **Effort:** S

### P1-009 — Add Redis to infra
- **AC:** ElastiCache or self-hosted; used as Django cache backend + Channels backend + Celery broker
- **Effort:** XS

### P1-010 — Add Celery + Beat workers
- **AC:** Celery worker process; Beat scheduler for periodic tasks; Flower or RabbitMQ admin for visibility
- **Effort:** S

---

## EPIC: Vendor-neutral data model

### P1-011 — Add `source_pbx` field to `CallRecord`
- **AC:** New field with choices: `3cx`, `cisco_cucm`, `ms_teams`, `webex_calling`, `zoom_phone`, `generic_sip`. Default `3cx`. Backfill existing rows
- **Effort:** XS

### P1-012 — Refactor `CallRecord` to vendor-neutral schema
- **AC:** Add normalized fields (caller_normalized, callee_normalized, call_type_normalized); keep raw vendor fields in JSON column `raw_data`. Migration path documented
- **Effort:** M

### P1-013 — Create `NormalizedCdr` dataclass for adapter outputs
- **AC:** Adapter framework expects this dataclass; conversion to/from `CallRecord` model trivial
- **Effort:** S

### P1-014 — Add `Tenant` alias for `Company` (forward-compat)
- **AC:** Code refers to `request.tenant` or `request.user.company` interchangeably
- **Effort:** XS

---

## EPIC: Multi-currency

### P1-015 — Create `Currency` model + seed data
- **AC:** SAR, AED, EGP, QAR, KWD, BHD, OMR, JOD, USD, EUR, PKR, INR seeded with code + name + symbol + decimals
- **Effort:** XS

### P1-016 — Add `currency` FK to `Company` model
- **AC:** Default SAR; migration backfills existing companies
- **Effort:** XS

### P1-017 — Refactor money fields to store amount + currency
- **AC:** All fields with monetary value (`call_rate`, `total_cost`, quotas, balances) display in company's currency
- **Effort:** M

### P1-018 — Currency formatting helper + template tags
- **AC:** `{{ amount|money:company.currency }}` renders "SAR 1,234.50" or "د.إ 4,567.00" with locale-aware formatting
- **Effort:** S

### P1-019 — Add currency exchange rate sync (daily cron)
- **AC:** Pull from open API (e.g., exchangerate.host); store historical rates; used for cross-currency reporting
- **Effort:** S

---

## EPIC: Tax engine

### P1-020 — Create `TaxRule` model
- **AC:** Fields: country, rate, effective_from/to, applies_to (SUBSCRIPTION/USAGE/BOTH); seed VAT 15% (KSA), 5% (UAE), 14% (EGY)
- **Effort:** XS

### P1-021 — Tax calculation in invoice generation
- **AC:** Invoice line items include subtotal + tax + total; multi-line tax breakdown
- **Effort:** S

### P1-022 — VAT registration capture per company
- **AC:** `vat_number` field; validated against country format; printed on invoices
- **Effort:** XS

### P1-023 — Reverse-charge VAT for cross-border B2B
- **AC:** When customer in different country than seller, no VAT applied; "Reverse charge" note on invoice
- **Effort:** S

---

## EPIC: Invoicing

### P1-024 — Create `Invoice` model + line items
- **AC:** Invoice → InvoiceLineItem (subscription | usage | add-on | one-time); status: DRAFT, ISSUED, PAID, OVERDUE, VOID; auto-numbered per company
- **Effort:** S

### P1-025 — PDF invoice generator
- **AC:** Uses WeasyPrint or ReportLab; company logo + branding; bilingual (Arabic + English); MENA address format; QR code for ZATCA
- **Effort:** M

### P1-026 — Recurring billing automation (Celery Beat)
- **AC:** Daily job generates invoices for all due subscriptions; sends email; stores PDF in S3
- **Effort:** S

### P1-027 — Email invoice delivery
- **AC:** Templated email (Arabic + English); PDF attached; payment link inline
- **Effort:** XS

### P1-028 — Customer self-serve portal
- **AC:** Customer logs in → views invoices → downloads PDF → pays via gateway → sees payment history
- **Effort:** M

### P1-029 — Dunning workflow
- **AC:** On failed payment: retry day 3, 7, 14; email reminder each; suspend service after day 21; auto-resume on payment
- **Effort:** S

### P1-030 — Credit notes + refunds
- **AC:** Issue credit note tied to invoice; reduce balance; reflect in self-serve portal
- **Effort:** S

### P1-031 — Promo codes / discounts
- **AC:** % off or fixed amount; applied at subscription start; expiry date; usage cap
- **Effort:** S

### P1-032 — ZATCA Phase 2 e-invoicing (KSA)
- **AC:** XML-structured invoice; QR code; cryptographic stamp; submitted to ZATCA portal in real-time. Use 3rd-party SDK
- **Effort:** M

---

## EPIC: Payment gateways

### P1-033 — Stripe integration
- **AC:** Cards + recurring; webhooks for payment_succeeded / payment_failed; SCA compliance; tested in sandbox + live
- **Effort:** S

### P1-034 — HyperPay integration (KSA + UAE)
- **AC:** Cards + Mada via HyperPay; recurring tokenization; webhooks; tested
- **Effort:** M

### P1-035 — PayTabs integration (KSA + UAE + Egypt)
- **AC:** Cards; alternative gateway; tested
- **Effort:** M

### P1-036 — Tap integration (KSA + UAE)
- **AC:** Cards + KNET + Apple Pay; tested
- **Effort:** S

### P1-037 — Manual bank transfer reconciliation
- **AC:** Customer marks invoice "paying by bank transfer"; uploads proof; admin confirms; auto-mark paid
- **Effort:** S

---

## EPIC: Arabic RTL UI

### P1-038 — Set up Django i18n + Arabic translation
- **AC:** All customer-facing strings wrapped in `{% trans %}`; `.po` file for Arabic populated by translator; deploy with both EN + AR
- **Effort:** M

### P1-039 — RTL CSS layer
- **AC:** When user language is Arabic: `<html dir="rtl">`; CSS uses logical properties (margin-inline-start, etc.); icons mirror appropriately
- **Effort:** M

### P1-040 — Arabic-aware date/number formatting
- **AC:** Optional Arabic numerals (٠١٢٣); Hijri calendar option in date pickers; Arabic month names
- **Effort:** S

### P1-041 — Translate all email templates
- **AC:** Each email template has AR + EN versions; user receives in their preferred language
- **Effort:** S

### P1-042 — Bilingual PDF reports
- **AC:** PDFs include parallel AR + EN columns or sections; works for invoices, fraud audit, top-extension reports
- **Effort:** S

---

## EPIC: Real-time wallboard

### P1-043 — Set up Django Channels + ASGI
- **AC:** `daphne` or `uvicorn` running ASGI; Redis as Channel layer
- **Effort:** S

### P1-044 — WebSocket consumer for wallboard
- **AC:** Authenticated WS endpoint; subscribes to tenant's wallboard group; receives JSON events
- **Effort:** S

### P1-045 — Event publishing from CDR pipeline
- **AC:** When CDR ingested or call ends → publish to Channels group → all connected wallboards updated <2s
- **Effort:** S

### P1-046 — Wallboard frontend (basic)
- **AC:** Tiles for: calls in progress, queue length, agents available, AHT, ASA, longest wait, recent calls ticker. Auto-refresh via WS.
- **Effort:** M

### P1-047 — Multi-screen / projection mode
- **AC:** Dark theme; large fonts; minimal chrome; URL with `?screen=1` → "TV mode"
- **Effort:** S

### P1-048 — Heatmap visualization (call volume by hour × day)
- **AC:** Color-coded grid; click cell drills into hour
- **Effort:** S

---

## EPIC: Public REST API

### P1-049 — Install + configure DRF + drf-spectacular
- **AC:** `/api/v1/` namespace; `/api/docs/` Swagger UI; `/api/schema.yml` OpenAPI spec
- **Effort:** XS

### P1-050 — JWT + API key authentication
- **AC:** JWT via `djangorestframework-simplejwt`; API keys via custom model with `key_hash`; permission classes per endpoint
- **Effort:** S

### P1-051 — Rate limiting
- **AC:** Per-API-key throttling via DRF + Redis backend; configurable per tier (free=100/min, paid=1000/min)
- **Effort:** XS

### P1-052 — API endpoints (CRUD subset)
- **AC:** Read endpoints for: companies, extensions, call records, quotas, invoices, rate cards. Write endpoints for: extensions create/update, quota assign, invoice mark-paid
- **Effort:** M

### P1-053 — Webhook subscriptions model
- **AC:** Per-tenant: register URL + event list (call.completed, invoice.paid, fraud.detected, etc.) + HMAC secret
- **Effort:** S

### P1-054 — Webhook delivery worker
- **AC:** Async delivery via Celery; retry 3x with exponential backoff; signature header `X-IPTPortal-Signature`; DLQ after final failure; admin can retry
- **Effort:** S

### P1-055 — API key management UI in customer portal
- **AC:** Create/revoke keys; see last-used timestamp; see rate-limit usage
- **Effort:** S

### P1-056 — Public API documentation site
- **AC:** Markdown docs + code examples (curl, Python, Node); hosted at developers.iptportal.com (or similar)
- **Effort:** S

---

## EPIC: Toll-fraud rule engine

### P1-057 — Create `FraudRule` model
- **AC:** Fields: rule_type (intl_spike, after_hours_intl, premium_destination, blacklist_country, velocity_calls, velocity_cost, velocity_duration), threshold, time_window, action (alert | disable_extension | block_route), severity (low/med/high/critical)
- **Effort:** XS

### P1-058 — Default rule pack (seeded for new tenants)
- **AC:** 8-12 sensible default rules per tenant; can be customized
- **Effort:** XS

### P1-059 — Real-time evaluator (runs on each CDR)
- **AC:** Async worker evaluates rules on incoming CDR; matches → create `FraudIncident` + dispatch alerts
- **Effort:** S

### P1-060 — Country / destination blacklist + premium-rate list
- **AC:** Configurable per company; default list seeded (high-risk premium destinations like satellite phones, certain country codes)
- **Effort:** XS

### P1-061 — Auto-disable extension on critical fraud
- **AC:** When critical rule fires + auto-disable enabled → toggle `Extension.disable_external_call` true; notify admin; log audit entry
- **Effort:** XS

### P1-062 — Fraud incident dashboard
- **AC:** Live list of incidents; severity color-coded; click to see CDRs that triggered; acknowledge / dismiss / mark false-positive
- **Effort:** S

### P1-063 — Free toll-fraud audit (lead-gen tool)
- **AC:** Public landing page → upload CSV of CDRs → run our rule engine → generate PDF report with findings + remediation suggestions → email to lead → CRM follow-up
- **Effort:** M

---

## EPIC: Notifications

### P1-064 — Channel adapters
- **AC:** Email (SES), SMS (Unifonic primary, Twilio fallback), Slack, MS Teams, in-app
- **Effort:** S

### P1-065 — Notification preferences per user
- **AC:** Each user picks channels per category (fraud, quota, billing, system); quiet hours config
- **Effort:** S

### P1-066 — Threshold alert rules engine
- **AC:** Per-tenant rules: "alert me if AHT > 5min", "alert if call cost > SAR 1000 in last hour"
- **Effort:** S

### P1-067 — Scheduled report email delivery
- **AC:** Per-report schedule (daily/weekly/monthly + day/time); generated via Celery; emailed as PDF + Excel
- **Effort:** S

---

## EPIC: Security baseline

### P1-068 — 2FA at login (TOTP)
- **AC:** `django-otp`; user enrolls via QR code (Google Authenticator / Authy compatible); enforced if user opts in or admin requires
- **Effort:** S

### P1-069 — Audit log model + middleware
- **AC:** Every authenticated state-change request logged: user, action, object, before/after diff, IP, user-agent, timestamp. Searchable by admin
- **Effort:** S

### P1-070 — IP whitelist per tenant
- **AC:** Optional per-tenant CIDR list; portal access blocked from non-listed IPs (admin can override)
- **Effort:** XS

### P1-071 — Role-based API permissions
- **AC:** API keys inherit user role; per-endpoint permission decorators
- **Effort:** S

### P1-072 — Password policy enforcement
- **AC:** Min length 12, complexity rules; password expiry config (per tenant); password history; admin-forced reset
- **Effort:** XS

### P1-073 — Session timeout configuration
- **AC:** Per-tenant configurable (default 8h); idle timeout; force-logout on password change
- **Effort:** XS

---

## Counts

| Epic | Tasks | Total effort |
|---|---|---|
| Hygiene & DevOps | 10 | ~3 weeks |
| Vendor-neutral data | 4 | ~1 week |
| Multi-currency | 5 | ~1.5 weeks |
| Tax engine | 4 | ~1 week |
| Invoicing | 9 | ~5 weeks |
| Payment gateways | 5 | ~3 weeks |
| Arabic RTL | 5 | ~2.5 weeks |
| Real-time wallboard | 6 | ~2.5 weeks |
| Public API | 8 | ~3 weeks |
| Toll-fraud | 7 | ~2.5 weeks |
| Notifications | 4 | ~1.5 weeks |
| Security | 6 | ~1.5 weeks |
| **Total** | **73** | **~28 person-weeks** |

With ~3.5 FTE × 12 weeks = 42 person-weeks available → comfortably achievable with buffer for bug-bash, customer onboarding, and unforeseen issues.
