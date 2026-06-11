"""Cisco CUCM CDR + CMR flat-file source (P5.1).

CUCM exports two flat CSVs: CDR (call facts) and CMR (per-stream media quality).
This adapter parses a CDR row into the canonical CallRecord shape and, when the
matching CMR row is supplied, joins the QoS metrics (jitter / latency / packet loss
/ MOS) that are 100% NULL today. Identity:
    globalCallID_callId + globalCallID_callManagerId -> external_id / correlation_id

There is no realtime push for CUCM — production ingest is an SFTP file poller
(fetch()), which needs a live CUCM SFTP drop to run end-to-end. The parsing
(normalize / merge_cmr) is pure and unit-testable with sample rows, which is what
is verified here.
"""
from decimal import Decimal, InvalidOperation

from acd.sources.base import CdrSource


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _dec(v):
    try:
        return Decimal(str(v))
    except (TypeError, ValueError, InvalidOperation):
        return None


def _epoch_to_dt(v):
    iv = _int(v)
    if not iv:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(iv, tz=timezone.utc)


def cucm_correlation_id(row):
    """Stable per-call id from the CUCM global call id pair."""
    call_id = (row.get('globalCallID_callId') or '').strip()
    cm_id = (row.get('globalCallID_callManagerId') or '').strip()
    if call_id and cm_id:
        return f"{cm_id}-{call_id}"
    return ''


class CiscoCucmCdrSource(CdrSource):
    transport = 'cucm_file'
    source_pbx = 'cucm'

    def fetch(self, **kwargs):  # pragma: no cover - needs live SFTP
        raise NotImplementedError(
            'CUCM SFTP polling requires live connection details; parsing is via '
            'normalize()/merge_cmr() on rows read from the dropped CSVs.')

    def normalize(self, raw):
        cid = cucm_correlation_id(raw)
        duration = _int(raw.get('duration'))
        return {
            'source_pbx': 'cucm',
            'external_id': cid,
            'correlation_id': cid,
            'call_time': _epoch_to_dt(raw.get('dateTimeConnect')
                                      or raw.get('dateTimeOrigination')),
            'caller': (raw.get('callingPartyNumber') or '').strip(),
            'callee': (raw.get('originalCalledPartyNumber')
                       or raw.get('finalCalledPartyNumber') or '').strip(),
            'from_no': (raw.get('callingPartyNumber') or '').strip(),
            'to_no': (raw.get('originalCalledPartyNumber') or '').strip(),
            'final_dn': (raw.get('finalCalledPartyNumber') or '').strip(),
            'duration': duration,
            'direction': None,
            'call_category': None,
            'total_cost': None,
            'ingest_transport': 'cucm_file',
            # QoS filled by merge_cmr()
            'mos': None, 'jitter_ms': None, 'packet_loss_pct': None,
            'latency_ms': None, 'codec': None,
        }

    @staticmethod
    def merge_cmr(canonical, cmr_row):
        """Join CMR media-quality fields onto an already-normalized canonical row.
        CMR carries cumulative jitter / latency / lost packets and (in newer CUCM)
        an MOS estimate. Mutates and returns canonical."""
        jitter = _int(cmr_row.get('maxJitter') or cmr_row.get('varVQMetrics'))
        latency = _int(cmr_row.get('latency'))
        lost = _int(cmr_row.get('numberPacketsLost'))
        rcvd = _int(cmr_row.get('numberPacketsReceived'))
        mos = cmr_row.get('mlqk') or cmr_row.get('mosLqk')
        if jitter is not None:
            canonical['jitter_ms'] = jitter
        if latency is not None:
            canonical['latency_ms'] = latency
        if lost is not None and rcvd:
            canonical['packet_loss_pct'] = round(lost / (lost + rcvd) * 100, 2)
        if mos is not None:
            canonical['mos'] = _dec(mos)
        return canonical
