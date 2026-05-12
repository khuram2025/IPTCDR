"""Vendor-neutral CDR shape + adapter ABC.

All PBX integrations produce ``NormalizedCdr`` instances. The CallRecord ORM
model maps 1:1 from this shape via :meth:`NormalizedCdr.to_call_record_kwargs`.

Adapters register themselves with the global ``AdapterRegistry`` so the rest
of the system can enumerate available PBX integrations without importing them
explicitly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable, Optional


@dataclass
class NormalizedCdr:
    """Vendor-neutral CDR row produced by every adapter."""

    # Identity / lineage
    source_pbx: str                                     # '3cx' | 'cisco_cucm' | 'ms_teams' | ...
    external_id: Optional[str] = None                   # Vendor-side unique ID (idempotency)
    correlation_id: Optional[str] = None                # Multi-leg call grouping
    company_id: Optional[int] = None

    # Parties
    caller: Optional[str] = None
    callee: Optional[str] = None
    from_dispname: Optional[str] = None
    to_dispname: Optional[str] = None
    final_dispname: Optional[str] = None

    # Timing
    call_time: Optional[datetime] = None
    time_answered: Optional[datetime] = None
    time_end: Optional[datetime] = None
    duration: Optional[int] = None                      # seconds

    # Routing / classification
    direction: Optional[str] = None                     # 'inbound' | 'outbound' | 'internal'
    from_type: Optional[str] = None
    to_type: Optional[str] = None
    final_type: Optional[str] = None
    reason_terminated: Optional[str] = None

    # Geo / cost (cost typically computed by rating engine, not adapter)
    country: Optional[str] = None
    call_category: Optional[str] = None
    call_rate: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None

    # Quality of Service
    mos: Optional[Decimal] = None
    jitter_ms: Optional[int] = None
    packet_loss_pct: Optional[Decimal] = None
    latency_ms: Optional[int] = None
    codec: Optional[str] = None

    # Original payload (for replay / debugging)
    raw_data: dict = field(default_factory=dict)

    def to_call_record_kwargs(self) -> dict:
        """Convert to kwargs accepted by ``CallRecord.objects.create``."""
        return {
            "source_pbx": self.source_pbx,
            "external_id": self.external_id,
            "correlation_id": self.correlation_id,
            "company_id": self.company_id,
            "caller": self.caller,
            "callee": self.callee,
            "from_dispname": self.from_dispname,
            "to_dispname": self.to_dispname,
            "final_dispname": self.final_dispname,
            "call_time": self.call_time,
            "time_answered": self.time_answered,
            "time_end": self.time_end,
            "duration": self.duration,
            "from_type": self.from_type,
            "to_type": self.to_type,
            "final_type": self.final_type,
            "reason_terminated": self.reason_terminated,
            "country": self.country or "Unknown",
            "call_category": self.call_category,
            "call_rate": self.call_rate or Decimal("0.00"),
            "total_cost": self.total_cost or Decimal("0.00"),
            "mos": self.mos,
            "jitter_ms": self.jitter_ms,
            "packet_loss_pct": self.packet_loss_pct,
            "latency_ms": self.latency_ms,
            "codec": self.codec,
            "raw_data": self.raw_data or None,
        }

    def to_dict(self) -> dict:
        return asdict(self)


class PbxAdapter(ABC):
    """Abstract base class for any PBX adapter.

    Subclasses declare ``source_pbx`` (matching ``CallRecord.SOURCE_PBX_CHOICES``)
    and implement at least one of:
      - ``fetch_cdrs(since)`` — for pull/poll adapters (CUCM SFTP, Teams Graph poll)
      - ``handle_event(payload)`` — for push adapters (3CX socket, Zoom webhook)
    """

    source_pbx: str = ""           # Override in subclass
    display_name: str = ""         # Human-readable name
    supports_realtime: bool = False
    supports_pull: bool = False

    def __init__(self, tenant_config: dict):
        self.config = tenant_config

    @abstractmethod
    def health_check(self) -> tuple[bool, str]:
        """Return (ok, message) describing connection status."""
        ...

    def fetch_cdrs(self, since: datetime) -> Iterable[NormalizedCdr]:  # pragma: no cover - optional
        """Pull CDRs since ``since``. Override if ``supports_pull`` is True."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support pull")

    def handle_event(self, payload: Any) -> Optional[NormalizedCdr]:  # pragma: no cover - optional
        """Process a push event (webhook / socket). Override if realtime."""
        raise NotImplementedError(f"{self.__class__.__name__} does not support push")

    def setup_wizard_steps(self) -> list[dict]:
        """Describe per-tenant setup steps for the UI wizard."""
        return []


class AdapterRegistry:
    """Process-wide registry of adapter classes."""

    _adapters: dict[str, type[PbxAdapter]] = {}

    @classmethod
    def register(cls, adapter_cls: type[PbxAdapter]) -> type[PbxAdapter]:
        if not adapter_cls.source_pbx:
            raise ValueError(f"{adapter_cls.__name__} must declare source_pbx")
        cls._adapters[adapter_cls.source_pbx] = adapter_cls
        return adapter_cls

    @classmethod
    def get(cls, source_pbx: str) -> Optional[type[PbxAdapter]]:
        return cls._adapters.get(source_pbx)

    @classmethod
    def all(cls) -> dict[str, type[PbxAdapter]]:
        return dict(cls._adapters)


def register_adapter(adapter_cls: type[PbxAdapter]) -> type[PbxAdapter]:
    """Decorator form of :meth:`AdapterRegistry.register`."""
    return AdapterRegistry.register(adapter_cls)
