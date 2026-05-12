# Phase 2 — Granular Task List (Months 3-6)

---

## EPIC: PBX adapter framework

### P2-001 — Define `PbxAdapter` abstract base class
- **AC:** Methods: `connect`, `fetch_cdrs(since)`, `supports_realtime`, `health_check`, `setup_wizard_steps`. Documented interface.
- **Effort:** S

### P2-002 — Adapter registry + dynamic loading
- **AC:** Adapters registered by entry-point or settings; new adapter pluggable without core code change
- **Effort:** S

### P2-003 — Adapter test harness
- **AC:** pytest fixtures with sample CDRs per vendor; CI runs adapter conformance tests
- **Effort:** S

### P2-004 — Per-adapter config UI in tenant settings
- **AC:** Tenant admin picks adapter type → sees vendor-specific config form → tests connection → enables
- **Effort:** M

### P2-005 — Adapter SDK doc for partners
- **AC:** Docs site explaining how to write a new adapter in ~200 lines; example skeleton
- **Effort:** S

---

## EPIC: Cisco CUCM adapter

### P2-006 — SFTP listener service
- **AC:** Per-tenant SFTP user; CUCM uploads CDR files; service detects new files; parses
- **Effort:** S

### P2-007 — CUCM CDR CSV parser (multi-version)
- **AC:** Supports CUCM 12.x, 14.x, 15.x; field mapping documented; gracefully handles unknown columns
- **Effort:** M

### P2-008 — CUCM → NormalizedCdr mapper
- **AC:** Caller, callee, duration, call_time, MOS, codec, gateway populated correctly
- **Effort:** S

### P2-009 — Customer setup guide for CUCM Billing App Server
- **AC:** Step-by-step doc + screenshots; ~10 minute setup
- **Effort:** XS

### P2-010 — End-to-end test with real CUCM (or simulator)
- **AC:** Test environment with CUCM 14 sandbox; CDRs flow end-to-end
- **Effort:** S

---

## EPIC: Microsoft Teams adapter

### P2-011 — Azure AD app registration & onboarding wizard
- **AC:** Tenant admin clicks "Connect Teams" → OAuth consent flow → app installed with `CallRecords.Read.All` permission
- **Effort:** S

### P2-012 — Microsoft Graph SDK setup
- **AC:** `msgraph-sdk-python` installed; auth flow tested
- **Effort:** XS

### P2-013 — Webhook subscription for callRecord
- **AC:** Subscribe to `/communications/callRecords` resource; renew before 3-day expiry; HTTPS endpoint receives notifications
- **Effort:** S

### P2-014 — Pull / delta-query fallback
- **AC:** Poll every 15 min; uses delta tokens to fetch only new records
- **Effort:** S

### P2-015 — Teams CallRecord → NormalizedCdr mapper
- **AC:** Handle peer-to-peer + group call; participants_v2 + organizer_v2 fields; session details
- **Effort:** M

### P2-016 — Auto Attendant & Call Queue analytics ingestion
- **AC:** Pull Teams Auto Attendant + Call Queue historical reports (Power BI template equivalent)
- **Effort:** S

### P2-017 — Setup doc + screenshots for Teams admins
- **AC:** ~5-min setup; permission justification text for admin consent
- **Effort:** XS

---

## EPIC: Webex Calling adapter

### P2-018 — Webex OAuth integration
- **AC:** Scopes: `spark-admin:calling_cdr_read`, `spark-admin:locations_read`, `analytics:read_all`. Onboarding wizard
- **Effort:** S

### P2-019 — CDR Stream consumer
- **AC:** Continuous consume from `analytics.webexapis.com/v1/cdr_feed`; resilient to disconnects
- **Effort:** S

### P2-020 — CDR Feed fallback (12-hour windows)
- **AC:** Backfill via CDR Feed if Stream gap detected; checkpoint cursor stored
- **Effort:** S

### P2-021 — Detailed Call Records webhook (Partner Hub)
- **AC:** Subscribe + HMAC verify + idempotent processing
- **Effort:** S

### P2-022 — Webex CDR → NormalizedCdr mapper
- **AC:** Field mapping documented; handles all call types
- **Effort:** S

---

## EPIC: Zoom Phone adapter

### P2-023 — Zoom Marketplace app
- **AC:** App published to Zoom Marketplace; OAuth scopes: `phone:read`, `phone:read:admin`, `phone_call_log:read:admin`, `phone_recording:read:admin`
- **Effort:** S

### P2-024 — Call logs REST API ingestion
- **AC:** Paginated fetch on schedule (every 5-15 min); checkpointed
- **Effort:** S

### P2-025 — Real-time webhook (call ended, recording ready)
- **AC:** Subscribe + verify + dispatch to processing pipeline
- **Effort:** S

### P2-026 — Multi-leg call reconstruction via call_uuid
- **AC:** Group call legs into single normalized record where appropriate
- **Effort:** S

### P2-027 — Zoom CDR → NormalizedCdr mapper
- **AC:** Field mapping documented
- **Effort:** S

---

## EPIC: Generic SIP / Asterisk / FreePBX

### P2-028 — Asterisk AMI / AGI listener
- **AC:** Connect to Asterisk Manager Interface; receive cdr events; transform
- **Effort:** S

### P2-029 — CSV import for batch CDR (any source)
- **AC:** Tenant uploads CSV → maps columns → preview → import → ongoing scheduled import via SFTP
- **Effort:** M

### P2-030 — Generic webhook receiver
- **AC:** Spec for any PBX to POST CDR JSON; documented
- **Effort:** XS

### P2-031 — Pre-built profiles for FreePBX, Yeastar, Grandstream
- **AC:** Click "I use Yeastar" → wizard with vendor-specific instructions
- **Effort:** S

---

## EPIC: LCR engine

### P2-032 — `Carrier` + `CarrierRateCard` models
- **AC:** Carrier metadata (name, technical contact, type); rate card with prefix → cost per minute
- **Effort:** S

### P2-033 — Rate-card CSV import + preview
- **AC:** Upload CSV → map columns → preview impact → confirm
- **Effort:** S

### P2-034 — LCR query function
- **AC:** Given destination prefix → return ranked carriers by cost; cache results
- **Effort:** S

### P2-035 — Routing recommendations dashboard
- **AC:** "Switch routes A → B for KSA mobile and save 12% next month"
- **Effort:** S

### P2-036 — Margin analysis per route
- **AC:** Compare carrier cost to customer-charged rate; flag negative margins
- **Effort:** S

### P2-037 — Per-customer carrier preferences
- **AC:** Override LCR for specific customers (quality > cost)
- **Effort:** S

---

## EPIC: Prepaid wallet + hybrid billing

### P2-038 — `Wallet` model per tenant
- **AC:** Balance, currency, low-balance threshold, auto-top-up rule
- **Effort:** XS

### P2-039 — Top-up via payment gateway
- **AC:** UI for manual top-up; auto-top-up when balance < threshold
- **Effort:** S

### P2-040 — Real-time balance deduction on call cost
- **AC:** Cost-calc worker deducts from wallet; if insufficient → block new calls or fall back to postpaid
- **Effort:** S

### P2-041 — Hybrid billing model
- **AC:** Postpaid up to credit limit, then prepaid wallet, then suspend. Configurable per tenant
- **Effort:** S

---

## EPIC: Reseller / White-label

### P2-042 — `Reseller` model + multi-tenant scope
- **AC:** Reseller has many Companies; reseller-admin role sees only own customers
- **Effort:** S

### P2-043 — Custom domain per reseller
- **AC:** Reseller adds CNAME → automated TLS via ACM/Let's Encrypt → portal accessible at custom domain
- **Effort:** M

### P2-044 — Branding system
- **AC:** Per-reseller: logo, favicon, primary color, accent color, login background, email sender, email template overrides
- **Effort:** S

### P2-045 — PDF invoice template per reseller
- **AC:** Reseller's logo + footer + bank details
- **Effort:** S

### P2-046 — Reseller commission engine
- **AC:** Per-reseller rev-share %; auto-calculated monthly; reseller dashboard shows earnings; payout workflow
- **Effort:** M

### P2-047 — Deal registration + MDF portal
- **AC:** Reseller registers deal → admin approves → discount auto-applied; MDF requests
- **Effort:** S

### P2-048 — Per-reseller pricing override
- **AC:** Reseller can set their own prices for end customers (within bounds)
- **Effort:** S

---

## EPIC: Drag-drop wallboard widgets

### P2-049 — Widget library (~10 widgets)
- **AC:** KPI tile, gauge, line/bar chart, table, ticker, agent grid, queue list, SLA gauge, leaderboard, heatmap
- **Effort:** M

### P2-050 — Drag-drop layout editor
- **AC:** Canvas; resize/rearrange widgets; save layout per user
- **Effort:** M

### P2-051 — Layout sharing (public read-only URL)
- **AC:** Generate shareable URL; can be opened on TV without login
- **Effort:** S

### P2-052 — Mobile-responsive layouts
- **AC:** Tablet + phone breakpoints
- **Effort:** S

---

## EPIC: KPI library + SLA + alerts

### P2-053 — Predefined KPI library
- **AC:** AHT, ASA, abandon rate, FCR, occupancy, queue length, SLA% — each as reusable widget config
- **Effort:** S

### P2-054 — Saved report templates per vertical
- **AC:** "Banking Daily Summary", "BPO Outbound Performance", etc.
- **Effort:** S

### P2-055 — SLA definitions + tracking
- **AC:** "X% answered within Y seconds"; live SLA gauge; alerts on breach
- **Effort:** S

### P2-056 — Threshold alert rules engine
- **AC:** Per-tenant rules: "alert if queue >20 calls", "alert if no answer in 10s on VIP queue"
- **Effort:** S

---

## EPIC: Tenant feature flags

### P2-057 — Integrate Unleash or GrowthBook
- **AC:** Self-hosted Unleash; SDK in Django; admin UI for flag management
- **Effort:** S

### P2-058 — Per-tenant flag overrides
- **AC:** Roll out feature to subset of tenants; A/B test new UI
- **Effort:** S

---

## Counts

| Epic | Tasks | Effort |
|---|---|---|
| Adapter framework | 5 | ~2 weeks |
| Cisco CUCM | 5 | ~2.5 weeks |
| MS Teams | 7 | ~4 weeks |
| Webex Calling | 5 | ~2.5 weeks |
| Zoom Phone | 5 | ~2.5 weeks |
| Generic SIP | 4 | ~2 weeks |
| LCR engine | 6 | ~2.5 weeks |
| Prepaid + hybrid | 4 | ~2 weeks |
| Reseller | 7 | ~4 weeks |
| Wallboard widgets | 4 | ~2.5 weeks |
| KPI + SLA | 4 | ~2 weeks |
| Feature flags | 2 | ~1 week |
| **Total** | **58** | **~30 weeks** |

With ~5 FTE × 12 weeks = 60 person-weeks available.
