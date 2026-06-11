"""Derive ACD fields from raw 3CX CDR columns."""
from datetime import timedelta

SYSTEM_DISPOSITIONS = frozenset({
    'failed', 'no_route', 'busy', 'declined', 'not_found', 'timeout',
    'src_participant_terminated', 'dst_participant_terminated',
    'terminatedbysrc', 'terminatedbydst',
})


def normalize_disposition(reason_terminated):
    if not reason_terminated:
        return None
    return reason_terminated.strip().lower()


def infer_direction(from_type, to_type, final_type):
    ft = (from_type or '').lower()
    tt = (to_type or '').lower()
    if ft == 'extension' and tt in ('line', 'provider', 'external', ''):
        return 'outbound'
    if tt in ('ivr', 'queue') or ft in ('line', 'provider', 'external'):
        return 'inbound'
    if ft == 'extension' and (tt == 'extension' or (final_type or '').lower() == 'extension'):
        return 'internal'
    return 'unknown'


def compute_wait_seconds(call_time, time_answered, time_end):
    if not call_time:
        return None
    end = time_answered or time_end
    if not end:
        return None
    delta = end - call_time
    return max(0, int(delta.total_seconds()))


def compute_talk_seconds(time_answered, time_end, duration):
    if duration is not None and duration >= 0:
        return duration
    if time_answered and time_end:
        return max(0, int((time_end - time_answered).total_seconds()))
    return None


def is_abandoned(time_answered, call_disposition):
    if time_answered is not None:
        return False
    if call_disposition in SYSTEM_DISPOSITIONS:
        return False
    return True


def enrich_call_record(record):
    """Populate derived ACD columns on a CallRecord instance (in-memory)."""
    record.call_disposition = normalize_disposition(record.reason_terminated)
    record.direction = infer_direction(record.from_type, record.to_type, record.final_type)
    record.wait_time = compute_wait_seconds(record.call_time, record.time_answered, record.time_end)
    record.ring_time = record.wait_time  # best available from CDR until agent-state feed
    record.abandoned = is_abandoned(record.time_answered, record.call_disposition)
    if record.time_answered and record.duration is None:
        talk = compute_talk_seconds(record.time_answered, record.time_end, record.duration)
        if talk is not None:
            record.duration = talk
    return record
