# Technical Architecture

Target architecture for an 18-month evolution from "Django monolith on one VM" to "horizontally scalable multi-PBX, multi-region, AI-augmented SaaS."

---

## 1. Current architecture (today)

```
[ 3CX socket server ] ──TCP──> [ Django app (1 VM) ] ──> [ PostgreSQL (same VM?) ]
                                                       └──> [ Static files served by Django ]

URLs: iptportal.channab.com (single tenant deploy via per-company port)
Users: email/password + OTP reset
Roles: superadmin / company_admin / user + custom roles
Billing: signal-driven cost calc on CallRecord.save()
```

**Issues:**
- Single point of failure
- Django dev server / single Gunicorn likely
- No queue / async worker visible
- No Redis / cache layer mentioned
- No CDN / no static asset optimization
- No staging environment
- Single region

---

## 2. Target architecture (M18)

```
                              ┌─ AWS me-central-1 (UAE) ────────────────┐
                              │   ┌─ STC Cloud (KSA, optional) ─────┐   │
                              │   │                                 │   │
[ Customer PBX (3CX/Cisco/    │   │   [ Load balancer + WAF ]       │   │
  Teams/Webex/Zoom/SIP) ]     │   │            │                    │   │
       │                      │   │   [ API Gateway / Kong ]        │   │
       │ CDR push / pull      │   │            │                    │   │
       ▼                      │   │   ┌────────┼────────────┐       │   │
[ Ingestion service ]         │   │   ▼        ▼            ▼       │   │
  - per-PBX adapter           │   │ [Web]    [API]       [Wallboard]│   │
  - normalize → CallRecord    │   │ Django   DRF         Channels   │   │
  - publish to Kafka topic    │   │   │       │            │ WS      │   │
       │                      │   │   └───┬───┘            │         │   │
       ▼                      │   │       │                │         │   │
[ Kafka / Redpanda ]          │   │   ┌───▼───┐    ┌──────▼─────┐  │   │
       │                      │   │   │ Redis │    │  PostgreSQL │  │   │
       ▼                      │   │   │ cache │    │  (multi-AZ) │  │   │
[ Async workers ]             │   │   │ + pub │    └──────┬──────┘  │   │
  - Celery / RQ               │   │   │ /sub  │           │          │   │
  - Cost calc                 │   │   └───────┘   ┌───────▼──────┐  │   │
  - Quota deduct              │   │               │ ClickHouse    │  │   │
  - Fraud rules               │   │               │ (analytics)   │  │   │
  - Notifications             │   │               └───────────────┘  │   │
  - AI pipeline               │   │                                  │   │
       │                      │   │   ┌─────────────────────────┐    │   │
       ▼                      │   │   │ S3-compatible storage   │    │   │
[ AI / STT / NLP services ]   │   │   │ - call recordings       │    │   │
  - Whisper (self-hosted)     │   │   │ - exports / reports     │    │   │
  - Azure Cognitive (Arabic)  │   │   │ - encrypted, lifecycled │    │   │
  - Sentiment models          │   │   └─────────────────────────┘    │   │
       │                      │   │                                  │   │
       ▼                      │   │   ┌─────────────────────────┐    │   │
[ ClickHouse for analytics ]  │   │   │ ElasticSearch / OpenSrch│    │   │
       │                      │   │   │ - recording search      │    │   │
       ▼                      │   │   │ - transcript search     │    │   │
[ Webhook outbound ]          │   │   └─────────────────────────┘    │   │
                              │   └─────────────────────────────────┘    │
                              └──────────────────────────────────────────┘
```

---

## 3. Key architectural decisions

### Multi-tenancy
- **Logical multi-tenancy** (single DB, `company_id` on every row) — current model, keep
- **Schema-per-tenant** for top 10-20 enterprise customers (PostgreSQL schemas) — for performance isolation
- **Dedicated single-tenant** deploys for govt customers (separate AWS account, separate DB)

### Async processing
- **Celery + Redis** as broker for async tasks (notifications, exports, AI pipelines)
- **Kafka / Redpanda** for high-volume event streams (CDRs, recordings)
- **Periodic tasks** via Celery Beat (quota resets, scheduled reports, fraud sweeps)

### Real-time (wallboards, alerts)
- **Django Channels** + Redis for WebSocket fan-out
- One WS per customer browser; broadcast updates from worker → Channels group → connected clients
- Server-sent events (SSE) as fallback

### Database strategy
- **PostgreSQL 15+** for transactional data (users, companies, CDRs <90 days, billing)
- **ClickHouse** for analytics queries (CDR aggregates, dashboards over months/years) — 10-100x faster than Postgres for OLAP
- **TimescaleDB extension** as alternative if avoiding new infra
- **Redis** for cache + session + Channels backend
- **OpenSearch / ElasticSearch** for recording transcript search

### Storage
- **S3-compatible** (AWS S3 me-central-1 primary, MinIO for self-hosted/govt)
- Lifecycle: hot (S3 Standard) → warm (S3 IA) at 30 days → cold (Glacier) at 90 days → delete per retention policy (or 10-year hold for SAMA bundle)
- All recordings encrypted with **per-tenant KMS keys**
- Customer-managed keys (BYOK) option for enterprise

### CDR ingestion abstraction
```python
# Pluggable adapter pattern
class PbxAdapter(ABC):
    @abstractmethod
    def connect(self, tenant_config): ...
    @abstractmethod
    def fetch_cdrs(self, since: datetime) -> list[NormalizedCdr]: ...
    @abstractmethod
    def supports_realtime(self) -> bool: ...

# Implementations
class ThreeCxSocketAdapter(PbxAdapter): ...
class CiscoCucmFtpAdapter(PbxAdapter): ...
class TeamsGraphAdapter(PbxAdapter): ...
class WebexCdrStreamAdapter(PbxAdapter): ...
class ZoomPhoneWebhookAdapter(PbxAdapter): ...
class GenericSipAdapter(PbxAdapter): ...

# Output: NormalizedCdr dataclass with vendor-neutral fields
```

### API
- **Django REST Framework** (DRF) for REST API
- **OpenAPI / Swagger** auto-generated docs at `/api/docs/`
- **JWT or OAuth2** for tokens; **API keys** for server-to-server
- **Rate limiting** via DRF throttling + Redis
- **Webhooks** (outbound) with HMAC signatures + retry policy

### Async / streaming
- **Kafka topics:**
  - `cdr.raw.<pbx_type>` — raw CDR events
  - `cdr.normalized` — after adapter normalization
  - `cdr.cost-calculated` — after rating engine
  - `recording.uploaded` — triggers transcription
  - `transcription.completed` — triggers sentiment/QA
  - `alert.fraud` / `alert.quota` / `alert.sla` — triggers notifications

### Fraud detection
- **Rule engine** (Phase 1) — declarative rules in DB, evaluated on each CDR
- **ML model** (Phase 3) — anomaly detection on call patterns per extension
- **Real-time** — fraud check happens on the cost-calc worker, before notification fan-out

### Recording pipeline
1. PBX or SBC streams audio (RTP fork or post-call upload)
2. Audio service receives, tags with call_id, encrypts, uploads to S3
3. Kafka event triggers transcription worker
4. Transcription → speaker diarization → sentiment → topic spotting → QA scoring
5. Results stored in ClickHouse (transcripts) + Postgres (metadata) + OpenSearch (full-text)

### AI cost control
- Per-tenant AI minute meter
- Hard caps configurable
- Notifications at 50% / 80% / 100%
- Auto-throttle or charge overages per pricing tier

### Multi-region / data residency
- **Primary region** at signup (KSA / UAE / EU / US)
- **No cross-region data movement** for govt/banking tenants
- **Read replicas** for reporting performance
- **DR region** in same regulatory jurisdiction

### Security
- **mTLS** between services
- **Vault** for secrets management
- **All PII encrypted** at rest
- **Audit log** to immutable storage (AWS CloudTrail equivalent)
- **WAF** at edge (Cloudflare or AWS WAF)
- **DDoS protection**
- **Pen-test** annually

### Observability
- **Structured JSON logs** → Loki or CloudWatch
- **Metrics** → Prometheus + Grafana
- **Tracing** → OpenTelemetry → Jaeger or Tempo
- **Error tracking** → Sentry
- **Synthetic monitoring** → Pingdom or Checkly
- **Per-tenant SLA dashboard** internal + customer-facing

### CI/CD
- **GitHub Actions** for build + test + deploy
- **Branch model:** main → staging → prod (auto on merge to main)
- **Database migrations:** zero-downtime (Django + django-pgmig or similar)
- **Feature flags** via Unleash / GrowthBook for tenant-scoped rollouts
- **Blue-green** or **canary** deploys for risky changes

### Deployment infra
- **Containerized** (Docker)
- **Kubernetes** (EKS) for production scale, or **ECS Fargate** for simpler ops in early days
- **Terraform** for infra-as-code
- **Auto-scaling** based on Kafka lag + HTTP RPS

---

## 4. Migration path (current → target)

### Step 1 — Stabilize (Month 0-1)
- `.gitignore` cleanup, kill `venv/` and `staticfiles/` from repo
- Add Gunicorn + Nginx in front of Django
- Add Redis for cache + Channels backend
- Add Celery + Beat workers
- Move static files to S3 + CloudFront/CloudFlare
- Add staging environment (same infra, smaller)

### Step 2 — API + real-time (Month 1-3)
- DRF + OpenAPI
- WebSocket wallboard via Channels
- Webhooks outbound system
- Alerts engine + fraud rule engine

### Step 3 — Data plane (Month 3-6)
- Add Kafka / Redpanda
- Refactor CDR ingestion to publish to Kafka
- Workers consume and write to Postgres + ClickHouse
- Migrate analytics queries to ClickHouse

### Step 4 — Multi-PBX (Month 3-6)
- Adapter framework
- One adapter at a time: Cisco CUCM → Teams → Webex → Zoom → generic SIP
- Adapter test harness with sample CDR fixtures

### Step 5 — Recording + AI (Month 6-12)
- Audio storage service
- Transcription pipeline (Whisper self-hosted + Azure Arabic)
- Sentiment / topic / QA workers
- Recording search via OpenSearch

### Step 6 — Multi-region (Month 12-18)
- Terraform per region
- Tenant region attribute → routing at edge (CloudFront / Route 53)
- Replicated control plane (small) per region; data plane fully isolated

### Step 7 — Compliance certifications (Month 12-18)
- SOC 2 Type I (M12) → Type II (M18)
- ISO 27001
- PCI DSS attestation (for recording bundle handling card data scenarios)
- KSA/UAE local certifications

---

## 5. Tech-stack inventory (target state)

| Layer | Tech |
|---|---|
| Language | Python 3.12+ (Django) + TypeScript (frontend) |
| Web framework | Django 5.x |
| API | Django REST Framework + drf-spectacular (OpenAPI) |
| WebSocket | Django Channels + daphne/uvicorn |
| Async tasks | Celery + Redis broker + Celery Beat |
| Streaming | Kafka or Redpanda |
| OLTP DB | PostgreSQL 15+ |
| OLAP DB | ClickHouse |
| Cache | Redis 7+ |
| Search | OpenSearch / ElasticSearch |
| Object storage | S3 (AWS) / MinIO (self-host) |
| Frontend | React (or keep Django templates + HTMX for cost) |
| Mobile | React Native or Flutter |
| AI/STT | Whisper (self-hosted) + Azure Speech (Arabic) + OpenAI API for summaries |
| Observability | Prometheus + Grafana + Loki + Sentry + OpenTelemetry |
| CI/CD | GitHub Actions + ArgoCD (k8s) or simpler ECR push |
| Infra | Terraform + (EKS or ECS Fargate) |
| CDN / WAF | CloudFront + AWS WAF (or Cloudflare) |
| Secrets | AWS Secrets Manager or HashiCorp Vault |
| Feature flags | Unleash or GrowthBook |
| Payments | Stripe + HyperPay + PayTabs + Tap + Mada |
| Email | AWS SES + Postmark fallback |
| SMS | Unifonic (KSA) + Twilio (global) |

---

## 6. Performance targets

| Metric | Target |
|---|---|
| Web TTFB | <200ms p50, <500ms p95 |
| API response | <100ms p50, <300ms p95 |
| Wallboard update latency | <2s (event → browser) |
| Dashboard query (90 days CDR) | <2s |
| CDR ingestion throughput | 1,000+ records/sec per worker |
| Recording transcription | <2x real-time (1 min audio in 30s) |
| Uptime SLA | 99.5% standard, 99.95% enterprise |
| Recovery Time Objective (RTO) | <1 hour |
| Recovery Point Objective (RPO) | <5 minutes |

---

## 7. Cost model (estimated, at 100 tenants)

| Component | Monthly cost (USD) |
|---|---|
| EKS cluster (3 nodes m6i.xlarge) | $400 |
| RDS Postgres (db.m6g.large multi-AZ) | $250 |
| ClickHouse Cloud (small) | $200 |
| Redis (ElastiCache cache.r6g.large) | $200 |
| Kafka (MSK serverless or self-hosted) | $200 |
| OpenSearch (small cluster) | $200 |
| S3 storage (10TB recordings) | $230 |
| CloudFront / WAF | $100 |
| Sentry + Grafana Cloud | $100 |
| AWS data transfer | $200 |
| **Total infra** | **~$2,080/mo** |
| AI / STT (per minute, pass-through) | varies |
| **Per-tenant infra cost** | **~$20/mo** at 100 tenants |

At SAR 1,499 (~$400) Business tier → **>95% gross margin on infra** before AI usage.
