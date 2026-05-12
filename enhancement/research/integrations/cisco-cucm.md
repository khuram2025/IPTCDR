# Integration — Cisco CUCM (Call Manager)

## Overview
Cisco Unified Communications Manager (CUCM) is the dominant enterprise IP-PBX. It exports CDR/CMR records via SFTP/FTP push to up to 8 customer/third-party billing servers (CUCM 14+). Versions 12-15 use the same CSV format with field additions.

## Architecture
```
[ CUCM cluster ] ─── push (SFTP/FTP) ───> [ Our SFTP listener ]
                                                  │
                                                  ▼
                                     [ Parser: CDR + CMR CSVs ]
                                                  │
                                                  ▼
                                     [ NormalizedCdr → Kafka ]
```

## Setup steps for customer
1. **Cisco Unified Serviceability** → **Tools** → **CDR Management**
2. Add **Billing Application Server** with our SFTP host, username, password (we provision per tenant)
3. **Service Parameters** → set **CDR Enabled Flag = True**
4. (Optional) **CDR Log Calls With Zero Duration Flag = True** if you want all attempts
5. Files arrive at our SFTP server within ~1 minute of call end (CDR file rotation interval is configurable)

## CDR file format
- CSV format
- One file per ~1 minute (configurable)
- Two file types:
  - **CDR (Call Detail Record)** — call metadata
  - **CMR (Call Management Record)** — quality stats (MOS, jitter, packet loss)
- Field count varies by CUCM version; common fields: ~140

## Key fields we map to NormalizedCdr
| CUCM field | NormalizedCdr field |
|---|---|
| origCalledPartyNumber | callee |
| callingPartyNumber | caller |
| dateTimeConnect / dateTimeDisconnect | call_time / end_time |
| duration | duration |
| origCause_value / destCause_value | termination_reason |
| origDeviceName | source_device |
| destDeviceName | dest_device |
| pkid | external_id (idempotency) |

CMR fields (joined by `pkid` to CDR):
| CMR field | NormalizedCdr field |
|---|---|
| varVQMetrics (parsed) | mos, jitter, packet_loss |
| codecType | codec |

## Adapter implementation notes
- Use `paramiko` or `asyncssh` for SFTP listener
- Per-tenant SFTP user under `chroot` jail
- Watch directory; on new file → enqueue parse job
- Parse with Python `csv` module
- Handle multi-version CSV column variation
- Idempotent: pkid uniqueness check
- Move processed files to `/processed/YYYY/MM/DD/` for audit

## Customer pain points (sales notes)
- **Cisco's own CAR tool is limited** — Cisco explicitly says CAR is not intended to replace third-party billing/accounting solutions
- Many customers struggle to set up SFTP correctly → our setup wizard is a value-add
- Multi-cluster deployments (typical large enterprise) need aggregation across clusters → handle gracefully

## Sources
- [Cisco CUCM Reporting & Billing Guide R14](https://www.cisco.com/c/en/us/td/docs/voice_ip_comm/cucm/callReportingBillingAdmin/14/cucm_b_reporting-billing-administration-guide-14/cucm_b_reporting-and-billing-administration-guide_chapter_01.html)
- [Cisco Export CDRs and CMRs R15](https://www.cisco.com/c/en/us/td/docs/voice_ip_comm/cucm/callReportingBillingAdmin/15/cucm_b_reporting-billing-administration-guide-15/cucm_b_reporting-and-billing-administration-guide_chapter_0101.html)
- [CUCM Call Detail Records 11.5 Overview](https://www.cisco.com/c/en/us/td/docs/voice_ip_comm/cucm/service/11_5_1/cdrdef/cucm_b_cucm-cdr-administration-guide-1151/cucm_b_cucm-cdr-administration-guide-1151_chapter_01.html)
- [Configuring External Billing Server on CUCM — UCCollabing](https://www.uccollabing.com/cisco-cucm-billing-server-configuration-externally/)
- [CDR Export to 3rd-Party — Cisco Community](https://community.cisco.com/t5/ip-telephony-and-phones/how-to-ftp-sftp-cdr-records-to-3rd-party-cdr-reporting-tool/td-p/1869679)
- [Enabling CDRs and CMRs in CCM — VoIP Detective](https://support.voipdetective.com/support/solutions/articles/48000618409-enabling-cdrs-and-cmrs-in-cisco-call-manager)
