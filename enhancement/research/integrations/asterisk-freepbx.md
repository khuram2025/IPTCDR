# Integration — Asterisk / FreePBX / Yeastar / Grandstream / Generic SIP

## Overview
Many MENA SMBs run Asterisk-based PBX (FreePBX, Issabel) or appliance vendors (Yeastar, Grandstream). These don't have unified APIs; common ingestion approaches:

1. **AMI (Asterisk Manager Interface)** — TCP socket, real-time events
2. **AGI (Asterisk Gateway Interface)** — call-flow scripts
3. **CDR CSV export** — file-based batch
4. **HTTP webhook** — if PBX firmware supports it
5. **Database read** (Asterisk CDR backend in MySQL/PostgreSQL)

## Recommended adapter approach
- **Primary:** AMI listener (real-time events, including `Cdr` event)
- **Fallback:** scheduled CSV import (SFTP)
- **Alternative:** generic HTTP webhook receiver (`POST /api/v1/cdr/inbound/<adapter_token>`)

## AMI integration
```python
# Pseudo-code
import asyncio
from panoramisk import Manager

manager = Manager(
    host=customer.pbx_host,
    port=customer.pbx_ami_port or 5038,
    username=customer.pbx_ami_user,
    secret=customer.pbx_ami_secret,
)

@manager.register_event('Cdr')
async def on_cdr(manager, message):
    cdr = NormalizedCdr(
        external_id=message['UniqueID'],
        caller=message['Source'],
        callee=message['Destination'],
        call_time=parse_datetime(message['StartTime']),
        duration=int(message['Duration']),
        billsec=int(message['BillableSeconds']),
        termination_reason=message['Disposition'],
        source_pbx='asterisk',
        raw_data=dict(message),
    )
    await publish(cdr)

await manager.connect()
```

## CSV import (FreePBX, Yeastar, Grandstream)
- Vendor exports CDR to CSV daily/hourly
- Customer SFTPs to our endpoint
- Our parser maps columns

## Pre-built profiles
We ship pre-configured adapter profiles for popular vendors so customers get a wizard:
- **FreePBX** (Asterisk-based) — AMI or DB
- **Issabel** — same
- **Yeastar S-series / P-series** — CDR export config
- **Grandstream UCM** — CDR export
- **3CX** (already supported)

## Setup wizard per vendor
- Customer picks vendor from dropdown → pre-filled config + screenshots specific to that vendor's admin UI

## Generic HTTP webhook spec
For any PBX or custom integration:
```
POST /api/v1/cdr/inbound/<tenant_token>
Content-Type: application/json
X-IPTPortal-Signature: hmac-sha256:...

{
  "external_id": "abc-123",
  "source_pbx": "custom",
  "caller": "+966501234567",
  "callee": "+966112345678",
  "call_time": "2026-05-12T10:30:00Z",
  "duration": 142,
  "termination_reason": "ANSWERED",
  "from_dispname": "Khalid",
  "to_dispname": "Reception"
}
```

## Adapter implementation notes
- For AMI: `panoramisk` (asyncio) or `pyst2` library
- For database read: minimize impact (read replica if available)
- Idempotency: prefer PBX-provided unique IDs (UniqueID for Asterisk)
- Handle reconnection (AMI drops are common)
- Multi-tenant: one connection pool per tenant, monitored

## Sales notes
- **Open-source PBX users** (Asterisk/FreePBX) often DIY their own dashboards → our value is "managed SaaS, AI included, MENA support"
- **Yeastar** has a strong APAC/MENA SMB base; partner channel exists
- **Grandstream** is popular in hospitality

## Sources
- [Using Open-Source Tools for VoIP Quality Monitoring — ICT Innovations](https://www.ictinnovations.com/utilizing-open-source-tools-for-voip-quality-monitoring-and-troubleshooting)
- [VoIPmonitor SIP/RTP analysis](https://www.voipmonitor.org/)
- [Multi-Tenant IP PBX — ASTPP](https://astppbilling.org/multi-tenant-ip-pbx)
- [Yeastar Multi-Tenant PBX](https://www.yeastar.com/multi-tenant-pbx/)
- [VitalPBX](https://vitalpbx.com/)
- [PBXware Multi-Tenant — Bicom](https://www.bicomsystems.com/products/pbxware-multi-tenant/)
