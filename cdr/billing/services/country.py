"""Resolve a callee/caller string to an ISO 3166-1 alpha-2 country code.

Used by fraud rules (blacklist / premium-destination) and by analytics that
need a normalized country code distinct from the existing free-text
``CallRecord.country`` field.
"""
from __future__ import annotations

import re

import phonenumbers

# Common Saudi prefixes treated specially because customers often store
# numbers without leading + or 00.
_SA_LOCAL_RE = re.compile(r'^0?5\d{8}$')
_SA_LANDLINE_RE = re.compile(r'^0?[1-46-7]\d{7,8}$')


def iso_country(number: str | None, default_region: str = 'SA') -> str | None:
    """Return ISO alpha-2 country code for ``number``, or None if undetermined.

    - Internal extensions (≤4 digits) → None
    - Local Saudi mobile/landline → 'SA'
    - International / E.164 → resolved via phonenumbers library
    """
    if not number:
        return None
    cleaned = re.sub(r'\D', '', number)
    if not cleaned or len(cleaned) <= 4:
        return None

    if _SA_LOCAL_RE.match(cleaned) or _SA_LANDLINE_RE.match(cleaned):
        return 'SA'

    candidate = number if number.startswith('+') else f'+{cleaned}'
    try:
        parsed = phonenumbers.parse(candidate, None)
    except phonenumbers.NumberParseException:
        try:
            parsed = phonenumbers.parse(number, default_region)
        except phonenumbers.NumberParseException:
            return None
    return phonenumbers.region_code_for_number(parsed)
