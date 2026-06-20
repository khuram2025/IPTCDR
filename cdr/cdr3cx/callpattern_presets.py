"""Calling Rules wizard — country catalog and smart pattern builder."""
from __future__ import annotations

import json
import re
from typing import Any


def build_smart_country_pattern(
    dial_code: str,
    min_digits: int = 8,
    max_digits: int = 12,
    *,
    trunk_zero: bool = False,
) -> str:
    """One regex covering how this country appears on outbound CDRs from KSA."""
    code = re.sub(r'\D', '', dial_code)
    if not code:
        return '^$'
    trunk = '0?' if trunk_zero else ''
    nat = rf'{trunk}\d{{{min_digits},{max_digits}}}'
    alts = [rf'00{code}{nat}', rf'\+{code}{nat}']
    # Bare country code — safe for 3+ digits, or 2-digit codes except NANP (1)
    if len(code) >= 3 or (len(code) == 2 and code != '1'):
        alts.append(rf'{code}{nat}')
    return '^(' + '|'.join(alts) + ')'


# Backward-compatible alias
def build_country_pattern(dial_code: str, min_digits: int = 8, max_digits: int = 12) -> str:
    return build_smart_country_pattern(dial_code, min_digits, max_digits)


def build_prefix_pattern(prefix: str) -> str:
    return prefix.strip()


def build_local_extension_pattern() -> str:
    return r'^\d{4}$'


def build_pattern_from_wizard(mode: str, **kwargs: Any) -> str:
    if mode == 'prefix':
        return build_prefix_pattern(kwargs.get('prefix', ''))
    if mode == 'local_ext':
        return build_local_extension_pattern()
    if mode == 'country':
        return build_smart_country_pattern(
            kwargs.get('dial_code', ''),
            int(kwargs.get('min_digits', 8)),
            int(kwargs.get('max_digits', 12)),
            trunk_zero=bool(kwargs.get('trunk_zero', False)),
        )
    if mode == 'regex':
        return (kwargs.get('regex') or '').strip()
    return build_prefix_pattern(kwargs.get('prefix', ''))


def regex_from_stored(pattern: str) -> str:
    from .models import CallPattern
    return CallPattern(pattern=pattern or '').get_regex_pattern()


def _national_example(min_digits: int, max_digits: int) -> str:
    length = max(min_digits, min(max_digits, 10))
    return '8' + '1' * (length - 1)


def country_dial_formats(
    dial_code: str,
    min_digits: int,
    max_digits: int,
    *,
    trunk_zero: bool = False,
    national_example: str | None = None,
) -> list[dict[str, str]]:
    code = re.sub(r'\D', '', dial_code)
    ex = national_example or _national_example(min_digits, max_digits)
    ex = ex[:max_digits]
    formats = [
        {'id': '00', 'label': '00 international', 'example': f'00{code}{ex}'},
        {'id': 'plus', 'label': '+ E.164', 'example': f'+{code}{ex}'},
    ]
    if len(code) >= 3 or (len(code) == 2 and code != '1'):
        formats.append({'id': 'bare', 'label': 'Country code prefix', 'example': f'{code}{ex}'})
    if trunk_zero:
        formats.append({
            'id': 'trunk0',
            'label': 'National leading 0',
            'example': f'00{code}0{ex}',
        })
    return formats


def country_sample_numbers(country: dict[str, Any]) -> list[str]:
    code = country['dial']
    min_d, max_d = country['min'], country['max']
    ex = _national_example(min_d, max_d)
    trunk = country.get('trunk_zero', False)
    samples = [
        f'00{code}{ex}',
        f'+{code}{ex}',
    ]
    if len(code) >= 3 or (len(code) == 2 and code != '1'):
        samples.append(f'{code}{ex}')
    if trunk:
        samples.append(f'00{code}0{ex}')
        samples.append(f'+{code}0{ex}')
    # Non-matching control
    samples.append('0501234567')
    return samples


def enrich_country(country: dict[str, Any]) -> dict[str, Any]:
    pattern = build_smart_country_pattern(
        country['dial'], country['min'], country['max'],
        trunk_zero=country.get('trunk_zero', False),
    )
    return {
        **country,
        'pattern': pattern,
        'formats': country_dial_formats(
            country['dial'], country['min'], country['max'],
            trunk_zero=country.get('trunk_zero', False),
        ),
        'samples': country_sample_numbers(country),
        'rule_name': f"International - {country['name']}",
    }


def get_country_by_iso(iso: str) -> dict[str, Any] | None:
    iso_u = (iso or '').upper()
    for c in COUNTRY_CATALOG:
        if c.get('iso', '').upper() == iso_u:
            return enrich_country(c)
    return None


def get_country_by_dial(dial: str) -> dict[str, Any] | None:
    d = re.sub(r'\D', '', dial or '')
    for c in COUNTRY_CATALOG:
        if c['dial'] == d:
            return enrich_country(c)
    return None


def country_catalog_enriched() -> list[dict[str, Any]]:
    return [enrich_country(c) for c in COUNTRY_CATALOG]


QUICK_RATE_CHIPS = [0.0, 0.20, 0.40, 0.60, 0.80, 1.00, 1.04, 1.50, 2.00, 3.00, 5.00]

PATTERN_MODES = [
    {'id': 'country', 'label': 'By country', 'icon': 'ri-earth-line', 'hint': 'Smart — auto-detects all dial formats'},
    {'id': 'prefix', 'label': 'Number prefix', 'icon': 'ri-hashtag', 'hint': 'e.g. 05, 011'},
    {'id': 'local_ext', 'label': 'Local extension', 'icon': 'ri-phone-line', 'hint': '4-digit internal'},
    {'id': 'regex', 'label': 'Advanced regex', 'icon': 'ri-code-s-slash-line', 'hint': 'Custom regex'},
]

RULE_PRESETS = [
    {
        'id': 'sa_mobile_05',
        'name': 'Saudi Mobile (05)',
        'mode': 'prefix',
        'prefix': '05',
        'call_type': 'mobile',
        'rate_hint': 0.40,
        'description': 'All numbers starting with 05',
        'samples': ['0501234567', '0559876543'],
    },
    {
        'id': 'sa_landline_01',
        'name': 'Saudi Landline (01x)',
        'mode': 'prefix',
        'prefix': '01',
        'call_type': 'national',
        'rate_hint': 0.20,
        'description': 'National landline prefixes 01x',
        'samples': ['0112345678', '0123456789'],
    },
    {
        'id': 'local_4digit',
        'name': 'Company extension',
        'mode': 'local_ext',
        'call_type': 'local',
        'rate_hint': 0.00,
        'description': '4-digit internal extensions',
        'samples': ['1005', '6148', '2001'],
    },
]

from .country_catalog import build_world_country_catalog

# Full world list (~245 countries) with curated rate hints where known
COUNTRY_CATALOG = list(build_world_country_catalog())

# Legacy alias for templates still using country_presets
COUNTRY_PRESETS = COUNTRY_CATALOG

TEST_NUMBERS_DEFAULT = [
    '0501234567', '0559876543', '0112345678', '1005',
    '006281234567890', '+6281234567890', '6281234567890',
    '00911234567890', '+911234567890',
]
