# Gap Analysis

Each gap is scored on:
- **Severity** (1-5): how badly it blocks growth
- **Effort** (1-5): how much work to close
- **Revenue impact** (1-5): how much new ARR it unlocks
- **Score** = Severity × Revenue / Effort (higher = do first)

---

## Critical gaps (Severity 5)

| # | Gap | Sev | Eff | Rev | Score | Phase |
|---|---|---|---|---|---|---|
| 1 | **Single PBX (3CX only)** — no Cisco / Teams / Webex / Zoom | 5 | 5 | 5 | 5.0 | P2 |
| 2 | **No invoicing / payment gateway** | 5 | 3 | 5 | 8.3 | P1 |
| 3 | **No call recording / storage / playback** | 5 | 4 | 5 | 6.3 | P3 |
| 4 | **No transcription / sentiment / AI** | 5 | 4 | 5 | 6.3 | P3 |
| 5 | **No public REST API + webhooks** | 5 | 2 | 4 | 10.0 | P1 |
| 6 | **No real-time wallboards** | 5 | 2 | 4 | 10.0 | P1 |

## High-priority gaps (Severity 4)

| # | Gap | Sev | Eff | Rev | Score | Phase |
|---|---|---|---|---|---|---|
| 7 | **No multi-currency support** | 4 | 1 | 4 | 16.0 | P1 |
| 8 | **No Arabic RTL UI** | 4 | 2 | 4 | 8.0 | P1 |
| 9 | **No fraud / toll-fraud alerting** | 4 | 2 | 4 | 8.0 | P1 |
| 10 | **No tax engine (VAT 15% per company)** | 4 | 1 | 4 | 16.0 | P1 |
| 11 | **No CRM integrations** | 4 | 3 | 4 | 5.3 | P4 |
| 12 | **No omnichannel (WhatsApp / chat / email / SMS)** | 4 | 4 | 4 | 4.0 | P3 |
| 13 | **No WFM (forecasting / scheduling)** | 4 | 4 | 3 | 3.0 | P3 |
| 14 | **No QA scorecards / coaching** | 4 | 3 | 4 | 5.3 | P3 |
| 15 | **No customer-facing self-serve portal** | 4 | 2 | 3 | 6.0 | P1 |
| 16 | **No reseller / white-label tier** | 4 | 3 | 5 | 6.7 | P2 |

## Mid-priority gaps (Severity 3)

| # | Gap | Sev | Eff | Rev | Score | Phase |
|---|---|---|---|---|---|---|
| 17 | **No mobile app (iOS / Android / PWA)** | 3 | 4 | 3 | 2.3 | P3 |
| 18 | **No call quality monitoring (MOS / jitter / packet loss)** | 3 | 3 | 3 | 3.0 | P3 |
| 19 | **No custom report builder (drag-drop)** | 3 | 4 | 3 | 2.3 | P4 |
| 20 | **No scheduled report email delivery** | 3 | 1 | 2 | 6.0 | P1 |
| 21 | **No SOC 2 / ISO 27001 readiness** | 3 | 5 | 4 | 2.4 | P4 |
| 22 | **No predictive dialer / power dialer** | 3 | 4 | 3 | 2.3 | P4 |
| 23 | **No AI voice agent / IVR bot** | 3 | 4 | 4 | 3.0 | P4 |
| 24 | **No DID / number inventory management** | 3 | 3 | 3 | 3.0 | P4 |
| 25 | **No data residency selection (KSA-only deploy)** | 3 | 4 | 3 | 2.3 | P4 |
| 26 | **No 2FA at login** | 3 | 1 | 1 | 3.0 | P1 |
| 27 | **No audit log** | 3 | 2 | 2 | 3.0 | P1 |
| 28 | **No SSO (SAML / OIDC)** | 3 | 3 | 3 | 3.0 | P3 |

## Hygiene gaps (always do first)

| # | Gap | Sev | Eff | Rev | Phase |
|---|---|---|---|---|---|
| 29 | `venv/` and `__pycache__/` committed to git | 5 | 1 | 0 | P1 |
| 30 | `staticfiles/` committed | 4 | 1 | 0 | P1 |
| 31 | `debug.log*` committed | 3 | 1 | 0 | P1 |
| 32 | No automated tests (no `tests.py` content evident) | 4 | 4 | 0 | P1+ |
| 33 | No CI/CD pipeline | 3 | 2 | 0 | P1 |
| 34 | No staging environment (looks like prod-only) | 3 | 2 | 0 | P1 |
| 35 | No structured logging | 2 | 2 | 0 | P1 |

---

## Sequencing logic

**Phase 1 (months 0-3) — Foundations & quick wins**
Pick gaps with score ≥ 6.0 and effort ≤ 3:
- #5 Public REST API (10.0)
- #6 Real-time wallboards (10.0)
- #7 Multi-currency (16.0)
- #10 Tax engine (16.0)
- #2 Invoicing + payments (8.3)
- #8 Arabic RTL (8.0)
- #9 Fraud alerts (8.0)
- #16 Reseller tier — defer to P2 (depends on multi-PBX)
- #15 Customer portal (6.0)
- #20 Scheduled reports (6.0)
- Plus all hygiene gaps (#29-#35)

**Phase 2 (months 3-6) — Multi-PBX**
- #1 Multi-PBX adapters (5.0) — biggest single bet
- #16 Reseller / white-label tier (6.7)
- LCR engine (new)
- Vendor-neutral data model refactor

**Phase 3 (months 6-12) — AI + CCaaS**
- #3 Call recording (6.3)
- #4 Transcription / sentiment (6.3)
- #14 QA scorecards (5.3)
- #12 Omnichannel (4.0)
- #13 WFM-lite (3.0)
- #17 Mobile app (2.3)
- #18 Call quality monitoring (3.0)
- #28 SSO (3.0)

**Phase 4 (months 12-18) — Platform & adjacent revenue**
- #11 CRM integrations (5.3)
- #19 Custom report builder (2.3)
- #21 SOC 2 (2.4)
- #22 Predictive dialer (2.3)
- #23 AI voice agent (3.0)
- #24 DID inventory (3.0)
- #25 Data residency (2.3)

→ Detailed sequencing in `07-roadmap.md`
→ Per-phase task breakdown in `tasks/phase{1,2,3,4}-tasks.md`
