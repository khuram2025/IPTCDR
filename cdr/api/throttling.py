"""DRF throttle scoped per API key tier.

DRF instantiates throttle classes before any request, so we can't resolve the
tier-specific rate at ``__init__``. Instead we defer until ``allow_request``
sees the API key on ``request.auth``.
"""
from rest_framework.throttling import SimpleRateThrottle


class ApiKeyScopedThrottle(SimpleRateThrottle):
    """Throttle keyed by API key, with rate determined by ``ApiKey.tier``."""

    cache_format = 'throttle_apikey_%(scope)s_%(ident)s'
    scope = 'api_key.paid'  # safe default; replaced per-request

    def __init__(self):
        # Don't call super().__init__() — it would resolve rate immediately.
        # Defer until we know the API key tier.
        self.rate = None
        self.num_requests = None
        self.duration = None

    def allow_request(self, request, view):
        api_key = getattr(request, 'auth', None)
        if api_key is None or not hasattr(api_key, 'tier'):
            return True  # not an API-key request — let other throttles handle it

        self.scope = f'api_key.{api_key.tier}'
        # Re-read live settings — DRF's class-level THROTTLE_RATES is captured
        # at import time and doesn't honour ``override_settings`` in tests.
        from rest_framework.settings import api_settings as drf_settings
        self.THROTTLE_RATES = drf_settings.DEFAULT_THROTTLE_RATES
        rate = self.THROTTLE_RATES.get(self.scope)
        if not rate:
            return True  # No rate configured for this tier → unlimited
        self.rate = rate
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        api_key = getattr(request, 'auth', None)
        if api_key is None or not hasattr(api_key, 'tier'):
            return None
        return self.cache_format % {'scope': self.scope, 'ident': api_key.pk}
