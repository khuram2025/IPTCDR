# Phase 1 — Foundations & Quick Wins (Months 0-3)

**Theme:** Plug worst gaps. Look enterprise-ready. Generate first new revenue.

---

## Goals

1. Become a real billing SaaS (invoicing + payments + tax)
2. Add multi-currency + Arabic RTL → unblock first non-KSA sale
3. Ship real-time wallboard → win demos
4. Launch toll-fraud add-on → new revenue line in <8 weeks
5. Public REST API + webhooks → enable integrations
6. Customer self-serve portal → reduce support load
7. Code-base hygiene + CI/CD + tests → production discipline

## Workstreams

### W1 — Hygiene & DevOps (Engineer: 1 backend + 0.5 DevOps, 4 weeks)
- `.gitignore`, remove tracked artifacts
- CI/CD pipeline (GitHub Actions: lint, tests, build, deploy)
- Staging environment (smaller but identical)
- Structured JSON logging
- Error tracking (Sentry)
- Health/readiness endpoints
- Automated test scaffolding (pytest-django + factories)

### W2 — Vendor-neutral data model (1 backend, 3 weeks)
- Refactor `CallRecord` to add `source_pbx`, normalize field names
- Migrate existing 3CX-specific fields to vendor-neutral schema
- Keep backward compatibility shim during migration
- Add `Tenant` (alias for Company) preparation for adapters

### W3 — Multi-currency + Tax engine (1 backend + 0.5 frontend, 3 weeks)
- `Currency` model + per-company currency setting
- `TaxRule` model (per country, per company override)
- VAT 15% (KSA) / 5% (UAE) / 14% (Egypt) defaults
- All money fields → store amount + currency
- Display formatting per locale (Arabic numerals, RTL aware)

### W4 — Invoicing + Payment gateways (2 backend + 1 frontend, 8 weeks)
- `Invoice` model + line items (subscription + usage + add-ons)
- PDF generator with company branding (use WeasyPrint or ReportLab)
- Stripe integration (cards, recurring)
- HyperPay integration (KSA)
- PayTabs integration (UAE + KSA)
- Tap integration (KSA + UAE)
- Mada (KSA debit) via HyperPay
- Recurring billing automation (Celery Beat)
- Dunning workflow (3 retries over 14 days then suspend)
- ZATCA Phase 2 e-invoicing (KSA) — XML, QR code, digital signature
- Customer self-serve portal (view + pay + download invoices)

### W5 — Arabic RTL UI (1 frontend, 4 weeks)
- i18n setup (Django i18n + React i18next if frontend-React)
- Arabic translation strings for all customer-facing text
- RTL CSS (logical properties, mirrored layouts)
- Arabic numerals option (٠١٢٣ vs 0123)
- Hijri calendar option in date pickers
- Bilingual PDF reports + invoices (Arabic + English columns)

### W6 — Real-time wallboard (1 backend + 1 frontend, 4 weeks)
- Django Channels + Redis backing
- WebSocket consumer for wallboard data
- Event publish from cost-calc / CDR-ingest workers
- Frontend wallboard: queue stats, agent status, SLA gauge, latest calls ticker
- Multi-screen projection mode (TV-friendly layout, dark theme)
- Heatmaps (call volume by hour × day-of-week)

### W7 — Public REST API + webhooks (1 backend, 4 weeks)
- DRF endpoints: companies, extensions, call records (read), quotas, invoices, rate cards
- OpenAPI/Swagger docs at `/api/docs/`
- API key model + per-key rate limiting (Redis)
- Webhook subscriptions (URL + events list + HMAC secret)
- Webhook delivery worker (retries + DLQ)
- API key management UI in customer portal

### W8 — Toll-fraud rule engine (1 backend + 0.5 frontend, 4 weeks)
- `FraudRule` model: rule type, threshold, action (alert/disable)
- Built-in rules: intl spike, after-hours intl, premium-rate destinations, blacklisted countries, velocity (calls/min, cost/hour, duration)
- Per-rule notification channels (email/SMS/Slack/Teams)
- Auto-disable extension on critical fraud
- Fraud incident dashboard + timeline + acknowledge/dismiss
- "Free toll-fraud audit" PDF report (lead-gen marketing tool)

### W9 — Notifications & alerts (0.5 backend, 2 weeks)
- Channel adapters: email (SES), SMS (Unifonic + Twilio fallback), Slack, MS Teams, push (later for mobile)
- Notification preferences per user
- Threshold alert rules engine
- Scheduled report email delivery (daily/weekly/monthly)

### W10 — Security baseline (1 backend, 3 weeks)
- 2FA at login (TOTP via `django-otp`)
- Audit log model + middleware (who did what when)
- IP whitelist option per tenant portal access
- Role-based API permissions
- Password policy enforcement
- Session timeout configuration

---

## Phase 1 timeline (12 weeks)

| Week | Workstreams in flight |
|---|---|
| 1-2 | W1 hygiene + W2 schema refactor start |
| 3-4 | W2 schema refactor complete + W3 multi-currency start + W10 security |
| 5-6 | W3 finish + W4 invoicing+payments + W5 Arabic start |
| 7-8 | W4 continues + W5 RTL UI + W6 wallboard start + W7 API start |
| 9-10 | W6 wallboard ship + W7 API ship + W8 fraud start + W9 notifications |
| 11-12 | W8 fraud ship + W4 ZATCA e-invoicing + bug bash + first beta customer onboarding |

---

## Engineering allocation

| Role | Headcount | Allocation |
|---|---|---|
| Backend Eng A | 1 | W1, W2, W7, W8 |
| Backend Eng B | 1 | W3, W4, W9, W10 |
| Frontend Eng | 1 | W3 (UI parts), W4 (portal), W5 (Arabic), W6 (wallboard), W7 (API key UI), W8 (fraud UI) |
| DevOps | 0.5 | W1, prod hardening |

→ 3.5 FTE for 12 weeks ≈ 42 person-weeks

---

## Acceptance criteria

| Criterion | Target |
|---|---|
| Repo size shrinks ≥80% (no venv/staticfiles tracked) | ✅ |
| All new code has tests; CI green | ≥70% coverage on new code |
| Multi-currency working for 3 currencies | ✅ |
| Arabic UI rendering RTL across all customer-facing pages | ✅ |
| First customer pays via Mada/HyperPay end-to-end | ✅ |
| Wallboard live in 5+ customer offices | ✅ |
| Public API documented; ≥1 external partner using it | ✅ |
| Toll-fraud add-on has ≥3 paying customers | ✅ |
| ≥1 paying customer outside KSA | ✅ |

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Schema refactor breaks existing data | Migrate in 2 steps with shim; backfill via management command; staging test first |
| Payment gateway integration delays (KYC) | Start KYC paperwork week 1; use Stripe in parallel as fallback |
| Arabic translation quality | Engage native Arabic copywriter; reviewer pass before each release |
| WebSocket scaling under load | Load-test wallboard with Locust early; Redis cluster ready by week 8 |
| Fraud rule false positives | Conservative defaults; "shadow mode" first 2 weeks before auto-disable |
| ZATCA e-invoicing complexity | Use 3rd-party ZATCA SDK (e.g., from local SaaS vendors) instead of building from scratch |
