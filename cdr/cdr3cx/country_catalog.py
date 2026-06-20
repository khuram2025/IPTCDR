"""World country catalog for Calling Rules wizard (phonenumbers-backed)."""
from __future__ import annotations

from functools import lru_cache

import phonenumbers
from phonenumbers import geocoder

# Curated SAR/min hints — merged over phonenumbers defaults
RATE_HINT_OVERRIDES: dict[str, float] = {
    'ID': 1.04, 'IN': 0.60, 'PK': 0.80, 'PH': 1.20, 'BD': 0.85,
    'EG': 0.90, 'AE': 0.70, 'JO': 0.75, 'LB': 1.10, 'TR': 1.00,
    'GB': 1.50, 'US': 1.80, 'CA': 1.80, 'LK': 1.10, 'NP': 1.00,
    'BR': 1.30, 'UG': 4.50, 'SD': 1.20, 'YE': 1.00, 'ET': 1.30,
    'KE': 1.20, 'NG': 1.40, 'ZA': 1.30, 'FR': 1.40, 'DE': 1.40,
    'IT': 1.40, 'ES': 1.30, 'CN': 1.20, 'MY': 0.90, 'TH': 0.95,
    'AU': 1.60,
}

# Digit-length overrides where lib metadata is too wide or known trunk behaviour
DIGIT_OVERRIDES: dict[str, dict] = {
    'ID': {'min': 9, 'max': 12},
    'IN': {'min': 10, 'max': 10},
    'PK': {'min': 10, 'max': 10},
    'PH': {'min': 10, 'max': 10},
    'BD': {'min': 10, 'max': 10},
    'EG': {'min': 9, 'max': 10, 'trunk_zero': True},
    'AE': {'min': 9, 'max': 9},
    'JO': {'min': 8, 'max': 9, 'trunk_zero': True},
    'LB': {'min': 7, 'max': 8, 'trunk_zero': True},
    'TR': {'min': 10, 'max': 10},
    'GB': {'min': 10, 'max': 10, 'trunk_zero': True},
    'US': {'min': 10, 'max': 10},
    'CA': {'min': 10, 'max': 10},
    'LK': {'min': 9, 'max': 9},
    'NP': {'min': 9, 'max': 10},
    'BR': {'min': 10, 'max': 11},
    'UG': {'min': 9, 'max': 9},
    'SD': {'min': 9, 'max': 9, 'trunk_zero': True},
    'YE': {'min': 8, 'max': 9, 'trunk_zero': True},
    'ET': {'min': 9, 'max': 9},
    'KE': {'min': 9, 'max': 9},
    'NG': {'min': 10, 'max': 10},
    'ZA': {'min': 9, 'max': 9, 'trunk_zero': True},
    'FR': {'min': 9, 'max': 9, 'trunk_zero': True},
    'DE': {'min': 10, 'max': 11, 'trunk_zero': True},
    'IT': {'min': 9, 'max': 10, 'trunk_zero': True},
    'ES': {'min': 9, 'max': 9},
    'CN': {'min': 11, 'max': 11},
    'MY': {'min': 9, 'max': 10, 'trunk_zero': True},
    'TH': {'min': 9, 'max': 9, 'trunk_zero': True},
    'AU': {'min': 9, 'max': 9, 'trunk_zero': True},
}

REGION_NAME_FALLBACK = {
    'AC': 'Ascension Island',
    'BL': 'Saint Barthélemy',
    'MF': 'Saint Martin',
    'TA': 'Tristan da Cunha',
    'XK': 'Kosovo',
}

SKIP_REGIONS = frozenset({'001'})


def iso_to_flag(iso: str) -> str:
    if not iso or len(iso) != 2 or not iso.isalpha():
        return '🌍'
    return ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in iso.upper())


def _region_display_name(region: str) -> str:
    if region in REGION_NAME_FALLBACK:
        return REGION_NAME_FALLBACK[region]
    try:
        example = phonenumbers.example_number(region)
        if example:
            name = geocoder.country_name_for_number(example, 'en')
            if name:
                return name
    except Exception:
        pass
    return region


def _digit_bounds(region: str, metadata) -> tuple[int, int, bool]:
    override = DIGIT_OVERRIDES.get(region, {})
    if 'min' in override and 'max' in override:
        trunk = override.get('trunk_zero', False)
        return override['min'], override['max'], trunk

    lengths: list[int] = []
    if metadata and metadata.general_desc and metadata.general_desc.possible_length:
        lengths = sorted(l for l in metadata.general_desc.possible_length if l > 0)

    if not lengths:
        lengths = [8, 12]

    min_d = max(4, min(lengths))
    max_d = min(15, max(lengths))
    if min_d > max_d:
        min_d, max_d = 8, 12

    trunk_zero = bool(
        override.get('trunk_zero')
        or (metadata and metadata.national_prefix == '0')
    )
    return min_d, max_d, trunk_zero


@lru_cache(maxsize=1)
def build_world_country_catalog() -> tuple[dict, ...]:
    """Return immutable tuple of country dicts sorted by name."""
    items: list[dict] = []
    for region in phonenumbers.SUPPORTED_REGIONS:
        if region in SKIP_REGIONS:
            continue
        try:
            dial = str(phonenumbers.country_code_for_region(region))
            if not dial or dial == '0':
                continue
            md = phonenumbers.PhoneMetadata.metadata_for_region(region)
            min_d, max_d, trunk_zero = _digit_bounds(region, md)
            name = _region_display_name(region)
            items.append({
                'iso': region,
                'flag': iso_to_flag(region),
                'name': name,
                'dial': dial,
                'min': min_d,
                'max': max_d,
                'rate_hint': RATE_HINT_OVERRIDES.get(region, 1.00),
                **({'trunk_zero': True} if trunk_zero else {}),
            })
        except Exception:
            continue
    items.sort(key=lambda c: c['name'].lower())
    return tuple(items)
