"""Real-time toll-fraud rule evaluator.

Each new ``CallRecord`` triggers ``evaluate_call`` which walks the active
``FraudRule`` set for that company and creates ``FraudIncident`` rows.

Rule semantics (``FraudRule.threshold`` interpretation):

| rule_type             | threshold meaning                              |
|-----------------------|------------------------------------------------|
| intl_spike            | # international calls in time_window_minutes  |
| after_hours_intl      | # international calls outside business hours  |
| premium_destination   | trigger if call to country in `countries`     |
| blacklist_country     | trigger if call to country in `countries`     |
| velocity_calls        | # calls per extension in window               |
| velocity_cost         | total cost per extension in window            |
| velocity_duration     | total duration (sec) per extension in window  |
| new_destination       | first ever call to a country (no history)     |
| long_intl             | duration in seconds (single call)             |
| concurrent_calls      | # active calls per extension                  |

Business hours are 08:00-18:00 in the company's local time (best-effort: we
treat server time as KSA AST until per-tenant timezone lands in P3).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import time
from decimal import Decimal
from typing import Optional

from django.db.models import Count, Sum
from django.utils import timezone

from accounts.models import Extension
from cdr3cx.models import CallRecord

from ..models import FraudIncident, FraudRule
from .country import iso_country

logger = logging.getLogger(__name__)

BUSINESS_START = time(8, 0)
BUSINESS_END = time(18, 0)


@dataclass
class _Match:
    rule: FraudRule
    summary: str
    detail: dict


# ---------------------------------------------------------------------------
# Rule evaluators — each returns a _Match or None
# ---------------------------------------------------------------------------


def _is_international(call: CallRecord) -> bool:
    if call.call_category and call.call_category.lower() == 'international':
        return True
    iso = iso_country(call.callee)
    return bool(iso) and iso != 'SA'


def _window_qs(call: CallRecord, minutes: int):
    """CallRecords in the same company in the trailing window."""
    if not call.call_time:
        return CallRecord.objects.none()
    window_start = call.call_time - timezone.timedelta(minutes=minutes)
    return CallRecord.objects.filter(
        company_id=call.company_id,
        call_time__gte=window_start,
        call_time__lte=call.call_time,
    )


def _eval_intl_spike(rule: FraudRule, call: CallRecord) -> Optional[_Match]:
    if not _is_international(call):
        return None
    count = sum(1 for c in _window_qs(call, rule.time_window_minutes).only('callee', 'call_category')
                if _is_international(c))
    if count >= rule.threshold:
        return _Match(rule, f"{count} international calls in {rule.time_window_minutes}m",
                      {'count': count, 'threshold': float(rule.threshold)})
    return None


def _eval_after_hours_intl(rule: FraudRule, call: CallRecord) -> Optional[_Match]:
    if not _is_international(call) or not call.call_time:
        return None
    local_time = timezone.localtime(call.call_time).time()
    if BUSINESS_START <= local_time < BUSINESS_END:
        return None
    if call.call_time.weekday() >= 5:  # Sunday-Thursday workweek would lower this; using Sat/Sun for now
        pass
    # Count after-hours intl calls in the window
    count = 0
    for c in _window_qs(call, rule.time_window_minutes).only('callee', 'call_category', 'call_time'):
        if _is_international(c):
            ct = timezone.localtime(c.call_time).time() if c.call_time else None
            if ct and not (BUSINESS_START <= ct < BUSINESS_END):
                count += 1
    if count >= rule.threshold:
        return _Match(rule, f"{count} after-hours intl calls in {rule.time_window_minutes}m",
                      {'count': count, 'threshold': float(rule.threshold), 'local_time': local_time.isoformat()})
    return None


def _eval_premium_destination(rule: FraudRule, call: CallRecord) -> Optional[_Match]:
    iso = iso_country(call.callee)
    if not iso or iso not in (rule.countries or []):
        return None
    return _Match(rule, f"Premium / high-risk destination: {iso}",
                  {'country_iso': iso, 'callee': call.callee})


def _eval_blacklist_country(rule: FraudRule, call: CallRecord) -> Optional[_Match]:
    return _eval_premium_destination(rule, call)  # same shape


def _eval_velocity_calls(rule: FraudRule, call: CallRecord) -> Optional[_Match]:
    if not call.caller:
        return None
    count = _window_qs(call, rule.time_window_minutes).filter(caller=call.caller).count()
    if count >= rule.threshold:
        return _Match(rule, f"{count} calls from {call.caller} in {rule.time_window_minutes}m",
                      {'count': count, 'caller': call.caller})
    return None


def _eval_velocity_cost(rule: FraudRule, call: CallRecord) -> Optional[_Match]:
    if not call.caller:
        return None
    total = _window_qs(call, rule.time_window_minutes).filter(caller=call.caller).aggregate(
        s=Sum('total_cost'))['s'] or Decimal('0')
    if total >= rule.threshold:
        return _Match(rule, f"Cost {total:.2f} from {call.caller} in {rule.time_window_minutes}m",
                      {'total_cost': str(total), 'caller': call.caller})
    return None


def _eval_velocity_duration(rule: FraudRule, call: CallRecord) -> Optional[_Match]:
    if not call.caller:
        return None
    total = _window_qs(call, rule.time_window_minutes).filter(caller=call.caller).aggregate(
        s=Sum('duration'))['s'] or 0
    if total >= rule.threshold:
        return _Match(rule, f"{total}s talk time from {call.caller} in {rule.time_window_minutes}m",
                      {'total_seconds': total, 'caller': call.caller})
    return None


def _eval_new_destination(rule: FraudRule, call: CallRecord) -> Optional[_Match]:
    iso = iso_country(call.callee)
    if not iso or iso == 'SA':
        return None
    seen = CallRecord.objects.filter(
        company_id=call.company_id,
        callee__startswith=call.callee[:4] if len(call.callee) >= 4 else call.callee,
    ).exclude(pk=call.pk).exists()
    if seen:
        return None
    return _Match(rule, f"First call ever to country {iso}",
                  {'country_iso': iso, 'callee': call.callee})


def _eval_long_intl(rule: FraudRule, call: CallRecord) -> Optional[_Match]:
    if not _is_international(call) or not call.duration:
        return None
    if call.duration >= rule.threshold:
        return _Match(rule, f"Long international call: {call.duration}s",
                      {'duration_seconds': call.duration, 'callee': call.callee})
    return None


def _eval_concurrent_calls(rule: FraudRule, call: CallRecord) -> Optional[_Match]:
    if not call.caller or not call.call_time:
        return None
    # A "concurrent call" = call by same caller whose answered/end window
    # overlaps the new call's start time.
    overlapping = CallRecord.objects.filter(
        company_id=call.company_id,
        caller=call.caller,
        call_time__lte=call.call_time,
        time_end__gte=call.call_time,
    ).exclude(pk=call.pk).count()
    if overlapping >= rule.threshold:
        return _Match(rule, f"{overlapping} concurrent calls from {call.caller}",
                      {'concurrent': overlapping, 'caller': call.caller})
    return None


_EVALUATORS = {
    'intl_spike':          _eval_intl_spike,
    'after_hours_intl':    _eval_after_hours_intl,
    'premium_destination': _eval_premium_destination,
    'blacklist_country':   _eval_blacklist_country,
    'velocity_calls':      _eval_velocity_calls,
    'velocity_cost':       _eval_velocity_cost,
    'velocity_duration':   _eval_velocity_duration,
    'new_destination':     _eval_new_destination,
    'long_intl':           _eval_long_intl,
    'concurrent_calls':    _eval_concurrent_calls,
}


# ---------------------------------------------------------------------------
# Action execution
# ---------------------------------------------------------------------------


def _execute_action(rule: FraudRule, call: CallRecord, incident: FraudIncident) -> str:
    """Run the rule's configured action. Returns the executed action name.

    Shadow mode short-circuits to 'shadow' so customers can validate rules
    before allowing destructive actions.
    """
    if rule.shadow_mode:
        return 'shadow'

    if rule.action == 'disable_extension' and call.caller:
        Extension.objects.filter(
            company_id=call.company_id, extension=call.caller,
        ).update(disable_external_call=True)
        logger.warning("[fraud] auto-disabled extension %s (rule=%s)", call.caller, rule.name)
        return 'disable_extension'

    if rule.action == 'block_route':
        # Hook for future SBC integration; record the intent for now.
        logger.warning("[fraud] block_route requested (rule=%s, call=%s)", rule.name, call.pk)
        return 'block_route'

    return 'alert'


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def evaluate_call(call: CallRecord) -> list[FraudIncident]:
    """Evaluate every active rule for the call's company. Returns created incidents."""
    if call.company_id is None:
        return []
    rules = FraudRule.objects.filter(company_id=call.company_id, is_active=True)
    incidents: list[FraudIncident] = []
    for rule in rules:
        evaluator = _EVALUATORS.get(rule.rule_type)
        if evaluator is None:
            continue
        try:
            match = evaluator(rule, call)
        except Exception:  # pragma: no cover - defensive
            logger.exception("Fraud evaluator %s crashed", rule.rule_type)
            continue
        if match is None:
            continue
        incident = FraudIncident.objects.create(
            company_id=call.company_id,
            rule=rule,
            severity=rule.severity,
            summary=match.summary,
            detail=match.detail,
            triggering_call=call,
        )
        incident.action_executed = _execute_action(rule, call, incident)
        incident.save(update_fields=['action_executed'])
        incidents.append(incident)
    return incidents
