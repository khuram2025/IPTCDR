# Vertical — Workforce Management (WFM)

## What & why
- **15-25% labor cost reduction** is the standard ROI quoted in 2026 WFM literature
- Mid-market is underserved — Calabrio dominates enterprise but SMB has fewer options
- Bundling WFM-lite into our Contact tier becomes a differentiator vs. Variphy / Tollring / Imagicle (none of which include WFM)

## Core capabilities

### Forecasting
- ML on historical call volume
- **Daily forecast within ±5%** of actual is best-in-class
- **Interval (30-min) forecast within ±10%** is best-in-class
- Statistical baselines (Holt-Winters, Prophet, ARIMA) work well
- Anticipate seasonality (Ramadan, Hajj, summer holidays in MENA)

### Scheduling
- Generate agent shifts that match forecasted demand
- Respect constraints: skills, preferences, max-hours, breaks, labor rules
- Optimize for SLA target while minimizing cost

### Adherence
- Real-time deviation from schedule
- Late, absent, in-wrong-state alerts
- Reports per agent, team, supervisor

### Intraday adjustment
- Real-time re-forecast when actual diverges from plan
- Suggest schedule changes (extend shifts, call in volunteers, send home)

### Time off / leave
- PTO request workflow
- Approval routing
- Auto-recompute schedule

### Skill-based routing
- Tag agents with skills (Arabic, English, banking, sales, technical)
- Route calls to best-fit available agent

## What to build

### Phase 3 (WFM-lite)
- Forecasting model (statistical first, ML later)
- Manual + auto-generated schedules
- Adherence dashboard
- Leave request workflow
- Skill-based routing config

### Phase 4 (advanced WFM)
- Multi-channel forecasting (voice + chat + email weighted)
- What-if scenario planning
- Calendar sync (Google / Outlook)
- Schedule swap workflow

## Pricing
- **+SAR 49-99/agent/mo** add-on to Contact tier
- Standalone WFM module: **SAR 199-299/agent/mo** (less common; most customers want bundle)

## MENA-specific WFM features
- **Sunday-Thursday work week** (KSA, Egypt) configurable as default
- **Friday/Saturday weekend** in shift patterns
- **Ramadan adjusted hours** — auto-detect Ramadan dates, apply per-tenant shift adjustments
- **Hajj season anomaly handling** — massive spike (govt, telco, hospitality) — pre-built playbook
- **Hijri calendar option** in scheduling
- **Local holidays** built into calendar (per-country)
- **Gender-segregated routing** (some KSA govt + healthcare requirements)

## Reference vendors

### Calabrio (leader)
- Forecasting + scheduling + adherence + AI-driven optimization
- 15-25% labor cost reduction quoted

### Verint WFM
- Enterprise leader

### NICE WFM
- Enterprise leader; QA + recording + WFM combined

### CommunityWFM
- Mid-market focused

### Vonage WFM
- Bundled with Vonage Contact Center

### Talkdesk WFM
- Bundled with Talkdesk CCaaS

### Scorebuddy WFM
- Modern entrant, QA + WFM

## Differentiation
- **Bundled with our analytics + recording + AI** (no separate WFM purchase)
- **MENA work-week defaults** (Sunday-Thursday, Hijri, Ramadan)
- **Pricing 30-50% below enterprise WFM** (Calabrio is enterprise-priced)
- **Lower onboarding burden** — works on data we already collect

## Sources
- [10 Best Call Center WFM Software 2026 — AmplifAI](https://www.amplifai.com/blog/call-center-workforce-management-wfm-software)
- [Best Call Center WFM Software 2026 — Capacity](https://capacity.com/blog/call-center-workforce-management-software/)
- [Best Call Center WFM Software 2026 — Lupahire](https://www.lupahire.com/blog/call-center-workforce-management-software)
- [26 Best Call Center WFM Software 2026 — CXLead](https://thecxlead.com/tools/best-call-center-workforce-management-software/)
- [Mastering WFM in Call Center — Nextiva](https://www.nextiva.com/blog/call-center-workforce-management.html)
- [Vonage WFM](https://www.vonage.com/contact-centers/features/workforce-management/)
- [Calabrio WFM](https://www.calabrio.com/products/workforce-management/)
- [Call Center Forecasting — CommunityWFM](https://www.communitywfm.com/forecasting)
- [Workforce Management Today](https://www.workforcemanagementtoday.com/)
- [Call Center WFM Software Guide 2026 — IntellCall](https://intellcall.com/blog/call-center-workforce-management-software-2026)
