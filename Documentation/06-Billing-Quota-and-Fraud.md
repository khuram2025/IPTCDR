# Billing, Quota & Fraud

This document audits the rating, quota-enforcement, multi-currency, tax, and toll-fraud subsystems of the connect.zentryc.com platform, separates what is *wired and working* from what is *schema-only plumbing*, and lays out the path from a single-tenant SAR call-accounting tool to a credible multi-tenant billing SaaS. Findings are grounded in the live code under `/home/ubuntu/3CX/cdr` and the production `cdr` database (verified 2026-06-05). For ingestion mechanics see [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md); for schema/index work see [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md); for the alerting runtime that all of this depends on see [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md); for sequencing see [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md).

## TL;DR / Key Takeaways

- **Quota is silently non-enforcing.** `UserQuota.deduct_balance()` (`cdr3cx/models.py:341`) had its over-balance guard removed — it always adds to `used_amount` and returns, never blocking. Only **2 of 779** quotas are currently over budget, not because spend is controlled but because nothing stops it.
- **Quota deduction races.** The deduction happens inside `CallRecord.save()` with **no `select_for_update`** (confirmed: zero occurrences in app code). Concurrent socket inserts for the same extension read-modify-write the same `UserQuota` row and lose updates.
- **The quota alert is dead code with the wrong recipient.** `send_quota_alert()` (`cdr3cx/models.py:360`) hardcodes `recipient = 'khuram2025@gmail.com'` (a developer address) **and has zero callers anywhere in the codebase** — alerts neither route correctly nor fire at all.
- **Quota reset is unreliable.** A `reset_quotas` management command exists (`cdr3cx/management/commands/reset_quotas.py`) but **no cron/systemd timer runs it** (verified: only `gunicorn`/`daphne`/`socket_server` services; no app jobs in `/etc/cron.d`). Reset happens only lazily on the next call save or via a manual admin action — non-deterministic and per-extension.
- **The rating engine is a flat per-pattern SAR rate.** No destination tiers, no time-of-day banding, no LCR, and **tax is never applied** — `TaxRule.calculate()` is referenced only in a seed migration, never in the cost path. Only **534,989 / 1,492,192 (35.8%)** calls carry a non-zero cost.
- **Multi-currency is modeled but not used.** `accounts.Currency` (13 rows) and `Company.currency` exist, but `CallPattern.rate_per_min`, `CallRecord.total_cost`, and `Quota.amount` are all implicitly SAR with no `currency` FK and no conversion.
- **There is no billing SaaS.** No invoice, payment, dunning, or gateway models exist (`billing/models.py` docstring concedes this). This is the largest greenfield gap.
- **Fraud detection works but nobody acts on it.** **18,361 incidents** accumulated in 24 days (2026-05-12 → 2026-06-05, ~765/day); **100% are `status='open'`** (zero acknowledged/resolved) and **every rule is in `shadow_mode=True`**, so no auto-disable/block action has ever executed. It is a noisy log, not a control.

---

## 1. Current State

### 1.1 Rating engine — pattern-based, flat, SAR-only

Rating is driven entirely by `CallPattern` (`cdr3cx/models.py:20`). Each pattern carries a `pattern` string, a `call_type` (mobile/national/international/local/unknown), and a single `rate_per_min` decimal "in SAR" (the field help text says so literally, `cdr3cx/models.py:33`). Costing runs synchronously inside `CallRecord.save()`:

1. `categorize_call()` (`models.py:148`) iterates `company.call_patterns` in regex order, first match wins, sets `call_category` + `call_rate`.
2. `calculate_total_cost()` (`models.py:174`) rounds duration **up to the whole minute** (`(duration + 59) // 60`) and multiplies by the rate.

This is a serviceable *zone-rate* model, but it is the weakest tier of telecom rating. There is no concept of a rate *plan* a tenant subscribes to, no per-destination-prefix tiering beyond the coarse `call_type`, no connection/setup fee, no minimum charge, no time-of-day or weekend banding, and no Least-Cost-Routing comparison across carriers. Whole-minute rounding is hardcoded; real plans need configurable increments (e.g. 1/1, 60/60, 30/6).

A second costing path exists in the `apply_pattern_to_call_records` `post_save` signal (`models.py:57`): saving *any* `CallPattern` re-prices **all** matching historical `CallRecord`s synchronously in a Python loop, each `record.save()` re-triggering the full heavy save (country lookup, fraud eval, quota deduction). On 1.49M rows this is an unbounded, blocking reprocessing storm. It also filters `to_type='Line'` with exact casing — see the flagship mixed-casing bug in [04-Data-Model-and-Database-Performance.md](04-Data-Model-and-Database-Performance.md).

Evidence of incompleteness: only **534,989 (35.8%)** of calls have `total_cost > 0`; **957,203 (64.2%)** are zero/null cost, because rating effectively only fires for outbound external calls that match a `Line` pattern.

### 1.2 Quota — modeled cleanly, enforced not at all

`Quota` is a tenant-level plan (amount + frequency: monthly/daily/weekly). `UserQuota` is the per-extension wallet (`total_amount`, `used_amount`, `last_reset`). There are **779 UserQuotas for 779 extensions** — full coverage. The model is reasonable; the behaviour is broken in four specific ways covered in §2.

### 1.3 Tax & multi-currency — schema present, logic absent

`billing.TaxRule` (`billing/models.py:19`) is a well-designed country/tenant VAT model with `effective_from/to` windows and a `calculate()` method. But `grep` proves `calculate()` is invoked **only** in `0002_seed_tax_rules_and_default_fraud_rules.py` — it is never called in any rating, quota, or report path. No call cost, no aggregate, and no (non-existent) invoice applies VAT today.

`accounts.Currency` (13 rows) and `Company.currency` / `Company.vat_number` exist, signalling clear multi-currency *intent*. Yet every monetary field downstream — `CallPattern.rate_per_min`, `CallRecord.call_rate`, `CallRecord.total_cost`, `Quota.amount`, `UserQuota.*` — is a bare `DecimalField` with no `currency` FK. The system is single-currency (SAR) in practice; a UAE tenant priced in AED would silently mix units.

### 1.4 Fraud — a working evaluator feeding an untriaged queue

`billing/services/fraud.py` is genuinely the most complete piece of the billing app: 10 rule evaluators (`intl_spike`, `velocity_cost`, `long_intl`, `concurrent_calls`, etc.), shadow-mode support, severity, and configurable actions (`alert` / `disable_extension` / `block_route`). It is wired via `post_save` on `CallRecord` (`billing/signals.py:15`) — i.e. it runs **synchronously in the socket ingest thread** for every call.

Production reality from the DB:

| Metric | Value |
|---|---|
| Total incidents | **18,361** |
| Date span | 2026-05-12 → 2026-06-05 (**24 days**) |
| Incident rate | **~765 / day** |
| `status='open'` | **18,361 (100%)** |
| `acknowledged` / `resolved` / `false_positive` | **0** |
| Rules total / `is_active` / `shadow_mode=True` | 18 / 18 / **18 (100%)** |

The signal is loud but inert: nobody triages (0% moved off `open`), and because every rule is in shadow mode, the `disable_extension` action on the two `critical` rules (`premium_destination`, `velocity_cost`) has never fired. Enforcement that *could* execute lives in `cdr3cx/blockExternalCall.py`, but that file is a standalone script with **hardcoded PBX credentials** (`USER_PASS = 'Smasco@445'`, `cdr3cx/blockExternalCall.py:11`) and is not invoked by the fraud action path (`fraud.py:222` flips a DB flag `disable_external_call` instead).

---

## 2. Correctness Bugs (fix first)

| # | Bug | Evidence | Severity | Effort |
|---|---|---|---|---|
| B1 | `deduct_balance()` never blocks over-quota spend | `cdr3cx/models.py:341` (guard removed, comment admits it) | **Critical** | S |
| B2 | Quota deduction races (no row lock) | `update_user_quota` reads/writes `UserQuota` with no `select_for_update`; 0 uses in app code | **Critical** | S |
| B3 | Quota alert hardcodes dev recipient **and is never called** | `cdr3cx/models.py:371` + 0 callers of `send_quota_alert` | **High** | S |
| B4 | Quota reset depends on a scheduler that is not running | `reset_quotas` command exists; no cron/systemd timer | **High** | M |
| B5 | `apply_pattern_to_call_records` re-saves all history synchronously | `cdr3cx/models.py:57-79` | **High** | M |
| B6 | Tax modeled but never applied | `TaxRule.calculate()` only in seed migration | **Medium** | M |
| B7 | Fraud queue 100% untriaged; all rules shadow-mode | DB: 18,361 open / 0 resolved | **Medium** | M |

### 2.1 Corrected quota deduction (B1 + B2)

The deduction must be atomic, row-locked, and must *decide* whether to allow the call's cost (enforcement happens out-of-band, but the wallet state must be correct). Move it out of `CallRecord.save()` into an idempotent enrichment step (see [03-CDR-Ingestion-and-3CX-Integration.md](03-CDR-Ingestion-and-3CX-Integration.md)) and make the write race-safe:

```python
from django.db import transaction
from django.db.models import F
from decimal import Decimal

def apply_cost_to_quota(extension, delta: Decimal) -> "QuotaResult":
    """Atomically apply a cost delta to an extension's wallet.
    `delta` may be negative when a record is re-priced downward."""
    with transaction.atomic():
        # SELECT ... FOR UPDATE locks the single wallet row for the txn,
        # serialising concurrent socket inserts for the same extension.
        wq = (UserQuota.objects
              .select_for_update()
              .get(extension=extension))

        wq.check_and_reset_if_needed()          # deterministic reset (see B4)
        new_used = wq.used_amount + delta
        over_budget = new_used > wq.total_amount

        # Atomic DB-side increment avoids read-modify-write on stale values.
        UserQuota.objects.filter(pk=wq.pk).update(used_amount=F('used_amount') + delta)

    if over_budget:
        enqueue_quota_breach(extension)          # async: alert + optional auto-disable
    elif wq.should_send_quota_alert_at(new_used):  # e.g. >=90%
        enqueue_quota_alert(extension, new_used)

    return QuotaResult(used=new_used, over_budget=over_budget)
```

Key changes vs. current: `select_for_update()` (B2), an explicit `over_budget` decision that drives enforcement instead of silently swallowing it (B1), and `F()`-based atomic increment so the value can never be clobbered by a concurrent thread. Whether an over-budget call is *blocked* is a policy decision — but blocking belongs in the PBX (via the [03](03-CDR-Ingestion-and-3CX-Integration.md) Call-Control path / `disable_external_call`), since CDRs arrive *after* the call. The portal's job is correct state + timely alert.

### 2.2 Corrected alert routing (B3)

Resolve the real owner, never a literal address, and actually call it. The model already has `should_send_quota_alert()` — wire it, fix the recipient, and dispatch through the notifications app so the channel is pluggable (email/SMS/WhatsApp — see [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md)).

```python
def quota_alert_recipients(extension) -> list[str]:
    """Resolve the real recipients for a quota alert, in priority order."""
    recipients = []
    owner = getattr(extension, 'user', None)        # extension owner
    if owner and owner.email:
        recipients.append(owner.email)
    # Fall back to the tenant's billing/admin contacts, never a hardcoded dev address.
    recipients += list(
        extension.company.users
        .filter(role__name__in=['billing_admin', 'company_admin'])
        .values_list('email', flat=True)
    )
    return [e for e in dict.fromkeys(recipients) if e]   # de-dupe, drop blanks

def send_quota_alert(extension, used_amount):
    to = quota_alert_recipients(extension)
    if not to:
        logger.warning("No quota-alert recipient for ext %s (company %s)",
                       extension.extension, extension.company_id)
        return
    notify(                                  # notifications app -> email/SMS/WhatsApp
        company=extension.company,
        template='quota_alert',
        to=to,
        context={'extension': extension.extension, 'used': used_amount},
    )
```

This removes the hardcoded `khuram2025@gmail.com` and the dead-code problem in one change. Note: because no Celery/cron worker runs in prod, "enqueue" must mean *evaluate-on-ingest* (synchronously fan to the notifications layer) until a real worker exists — see [08](08-Realtime-Alerts-and-Notifications.md) and [12](12-Migration-Plan-and-Phased-Roadmap.md).

### 2.3 Deterministic quota reset (B4)

Today reset is lazy (`check_and_reset_if_needed()` only runs when a *new call for that extension* arrives) — an idle extension never resets, and a busy one resets at a random call-time. Replace with a scheduled sweep. Until a Celery beat exists, the lowest-risk fix is a systemd timer invoking the existing command:

```ini
# /etc/systemd/system/reset-quotas.timer  (runs hourly; the command is idempotent)
[Timer]
OnCalendar=hourly
Persistent=true
[Install]
WantedBy=timers.target
```
```ini
# /etc/systemd/system/reset-quotas.service
[Service]
Type=oneshot
WorkingDirectory=/home/ubuntu/3CX/cdr
ExecStart=/home/ubuntu/3CX/cdr/venv/bin/python manage.py reset_quotas
```

`reset_quotas` already calls `check_and_reset_if_needed()` per wallet (`reset_quotas.py:12`), and `should_reset()` already computes the next boundary by frequency, so an hourly idempotent sweep is safe. (Strategically, fold this into the same worker that runs scheduled reports and alert evaluation — see [08](08-Realtime-Alerts-and-Notifications.md)/[12](12-Migration-Plan-and-Phased-Roadmap.md).)

### 2.4 De-risk pattern reprocessing (B5)

The `apply_pattern_to_call_records` signal must not re-save millions of rows inline on the request thread. Target: a bounded, queued backfill (management command or worker task) that uses `bulk_update` on `call_category/call_rate/total_cost` and **does not** re-trigger `CallRecord.save()` (so it skips re-running fraud eval and country lookup). This is also where the historical cost-recalculation for a corrected rate plan belongs.

---

## 3. Rating-Engine Maturity Gaps

| Capability | Current | Target | Severity | Effort |
|---|---|---|---|---|
| Destination tiering | coarse `call_type` (5 values) | prefix/longest-match rate table per rate plan | High | L |
| Rate plan as a subscribable entity | none (patterns are per-company) | `RatePlan` a tenant/extension subscribes to | High | L |
| Time-of-day / weekend banding | none | peak/off-peak/weekend rate bands | Medium | M |
| Billing increment / min charge / setup fee | hardcoded whole-minute | configurable increment (1/1, 60/60), connect fee, min charge | Medium | M |
| Least-Cost Routing analytics | none | carrier rate decks + LCR comparison report | Medium | L |
| Tax application | modeled, never applied | apply `TaxRule` at invoice/aggregate time | Medium | M |
| Multi-currency | modeled, not used | `currency` FK on every money field + FX table | High | L |

**Multi-currency, concretely.** Add a `currency` FK (default SAR via data migration) to `CallPattern`, `RatePlan`, and the future `Invoice`; store an FX snapshot per invoice so historical invoices never re-value. Keep `total_cost` in the *tenant's* currency and never mix. The `money_tags` template helper already exists for display formatting — extend it to format by `Company.currency.symbol`/`decimals`.

**Rating as a pipeline, not a `save()` side-effect.** Re-home rating into a stateless `rate(call) -> RatedCall` service that takes the normalized leg, selects the tenant's active `RatePlan`, does longest-prefix match, applies band + increment + min-charge, and returns `(category, rate, base_cost, currency)`. Tax is applied later at aggregation/invoicing, not per call. This makes rating testable, re-runnable for historical re-pricing, and vendor-neutral (3CX/Cisco/Teams all feed the same `RatedCall`).

---

## 4. The Path to a Real Billing SaaS

The prior business-strategy set (`/home/ubuntu/3CX/enhancement/*.md`, the "IPT Bill" product line) describes the *commercial* shape; pricing and packaging are not restated here. From an engineering standpoint the platform today is a **call-accounting** system (it tells you what calls *cost*) but not a **billing** system (it cannot *invoice or collect*). The missing spine:

| Component | Status | Notes |
|---|---|---|
| Rate plans | Implicit (patterns) | Promote to first-class `RatePlan` + `RatePlanItem` (prefix → rate/band/increment) |
| Invoices | **None** | `Invoice` (period, tenant, currency, FX snapshot) + `InvoiceLine` (usage rollup + subscription + tax) |
| Tax on invoices | **None** | Apply `TaxRule.calculate()` on the invoice subtotal (already built) |
| Payments | **None** | `Payment` ledger; gateway-agnostic (Stripe/HyperPay/Tap/PayTabs for MENA) |
| Dunning / credit control | **None** | Overdue stages → reminder emails → suspend (reuse the quota/disable path) |
| Statement / customer portal | **None** | Per-tenant invoice/usage view; ties into RBAC in [09-Security-and-Compliance.md](09-Security-and-Compliance.md) |

`billing/models.py`'s own docstring concedes this: *"Invoices and payment gateway records will land in subsequent migrations once gateway integration work begins."* That work has not begun. Recommended sequencing: (1) fix quota correctness (§2, days), (2) make rating a pipeline + apply tax to aggregates (§3, weeks), (3) introduce `Invoice`/`InvoiceLine` generated by a scheduled rollup job, (4) add a payment ledger + one MENA-appropriate gateway, (5) dunning that reuses the §2 enforcement path. This is the phased plan detailed in [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md).

A key design point for multi-vendor (see [10-Multi-Vendor-and-Target-Architecture.md](10-Multi-Vendor-and-Target-Architecture.md)): invoicing must read from the *normalized, rated* `CallRecord`/`RatedCall`, never from vendor-specific fields, so a tenant running 3CX + Cisco CUCM gets one consolidated invoice.

---

## 5. Fraud-Engine Assessment & Tuning

The evaluator design is sound; the *operating model* is the problem. 18,361 untriaged incidents in 24 days with zero resolutions means the queue is being ignored — classic alert fatigue from un-tuned thresholds running in shadow mode with no closure workflow.

**Recommendations:**

1. **Move evaluation off the ingest thread.** Today `evaluate_call` runs synchronously per `CallRecord.save()` (`billing/signals.py`), and several evaluators scan the window over the **unindexed `call_time`** column (`fraud.py:71`) on 1.49M rows — a sequential scan per call. This compounds the heavy-save problem in [04](04-Data-Model-and-Database-Performance.md). Add the composite `(company_id, call_time)` index and move evaluation to the async enrichment step.
2. **Tune to cut noise.** With ~765/day, thresholds are too tight (the bulk are `high`/`medium`). Calibrate per tenant against historical baselines; the `shadow_mode` flag is the right tool — keep noisy rules in shadow, but only *graduate* a rule out of shadow once its precision is acceptable.
3. **Add a closure workflow + SLA.** The `FraudIncident.status` machine (`open → acknowledged → resolved → false_positive`) and the incident dashboard exist — they are simply unused. Require triage, track false-positive rate per rule, and feed that back into tuning. An incident that auto-resolves after N days with no related calls should close itself.
4. **Make at least the `critical` rules act.** `premium_destination` and `velocity_cost` are configured to `disable_extension` but are stuck in shadow. After tuning, graduate these two so toll-fraud is actually *stopped*, not just logged. Route the action through a hardened enforcement service — **not** the credential-hardcoded `blockExternalCall.py` — using OAuth client-credentials and per-tenant secrets (see [09-Security-and-Compliance.md](09-Security-and-Compliance.md)).
5. **Fix incident notification delivery.** `FraudIncident.notification_dispatched` exists but, like quota alerts, there is no running worker to dispatch on. Route fraud notifications through the same alert engine and recipient-resolution logic built in §2.2 / [08-Realtime-Alerts-and-Notifications.md](08-Realtime-Alerts-and-Notifications.md), so a `critical` toll-fraud incident pages the tenant's security/billing contact in real time.

---

## 6. Summary of Recommendations

1. **Days:** Fix B1–B4 — make `deduct_balance` lock + decide, route the quota alert to the real owner and actually call it, schedule `reset_quotas` via a systemd timer. These are small, isolated, and restore the product's core promise (spend control).
2. **Weeks:** Re-home rating and fraud evaluation out of `CallRecord.save()` into an idempotent enrichment step ([03](03-CDR-Ingestion-and-3CX-Integration.md)); add the `(company_id, call_time)` index ([04](04-Data-Model-and-Database-Performance.md)); de-risk the historical-reprice signal; tune fraud thresholds and stand up the triage workflow.
3. **Quarter+:** Promote patterns to `RatePlan`, add currency FKs + FX, apply `TaxRule` at aggregation, and build the `Invoice`/`Payment`/dunning spine that turns call-accounting into billing — per [12-Migration-Plan-and-Phased-Roadmap.md](12-Migration-Plan-and-Phased-Roadmap.md).
