"""Vendor-neutral CDR source adapter interface (P1.4 / P5).

Every PBX family (3CX socket, 3CX XAPI, Cisco CUCM file, future cloud) implements
the same contract: fetch raw rows, normalize each to the canonical dict, and let a
shared upsert path write CallRecords. PBX quirks (field order, casing, version) stay
inside the adapter — the rest of the system only sees canonical records.
"""
from abc import ABC, abstractmethod

# The canonical CallRecord superset (P1.1) a normalize() must populate (nullable
# where a given vendor doesn't provide the field).
CANONICAL_FIELDS = (
    'source_pbx', 'external_id', 'correlation_id', 'call_time', 'caller', 'callee',
    'from_no', 'to_no', 'final_dn', 'duration', 'direction', 'call_category',
    'total_cost', 'ingest_transport',
    # QoS (CUCM CMR / DB-pull feeds populate these; socket leaves them null)
    'mos', 'jitter_ms', 'packet_loss_pct', 'latency_ms', 'codec',
)


class CdrSource(ABC):
    """fetch -> normalize -> (correlate) -> upsert, one PBX family per subclass."""

    #: short tag stored on CallRecord.ingest_transport
    transport = 'unknown'
    source_pbx = 'unknown'

    def __init__(self, company):
        self.company = company

    @abstractmethod
    def fetch(self, **kwargs):
        """Yield raw vendor rows (dicts) for the requested window/cursor."""
        raise NotImplementedError

    @abstractmethod
    def normalize(self, raw):
        """Map one raw vendor row to a canonical dict keyed by CANONICAL_FIELDS."""
        raise NotImplementedError

    def canonical(self, raw):
        """normalize() + guarantee the source/transport tags are stamped."""
        row = self.normalize(raw)
        row.setdefault('source_pbx', self.source_pbx)
        row.setdefault('ingest_transport', self.transport)
        return row
