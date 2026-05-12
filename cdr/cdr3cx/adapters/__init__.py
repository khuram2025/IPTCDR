"""PBX ingestion adapter framework.

Each adapter normalises vendor-specific CDRs into ``NormalizedCdr`` instances
and pushes them downstream (Kafka topic in target architecture; direct DB
write in Phase 1). All adapters share the ABC defined in :mod:`base`.
"""
from .base import NormalizedCdr, PbxAdapter, AdapterRegistry, register_adapter

__all__ = ["NormalizedCdr", "PbxAdapter", "AdapterRegistry", "register_adapter"]
