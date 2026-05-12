"""Security middleware:

- AuditLogMiddleware: writes one ``AuditLogEntry`` per state-changing request
- IpWhitelistMiddleware: blocks tenant portal access from non-allowed IPs
- DynamicSessionTimeoutMiddleware: applies per-tenant session-timeout policy
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.http import HttpResponseForbidden

from .models import AuditLogEntry, CompanyIpWhitelist, CompanySecurityPolicy

logger = logging.getLogger(__name__)


# Paths that should NEVER be audited (high-volume, low-value)
_AUDIT_EXEMPT_PREFIXES = (
    '/static/', '/media/', '/favicon.ico',
    '/api/v1/health/',
    '/realtime/',  # WS handled separately; HTTP GETs aren't state changes
)

_AUDITED_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


def _client_ip(request) -> str | None:
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class AuditLogMiddleware:
    """Records POST/PUT/PATCH/DELETE requests for compliance audit."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._maybe_log(request, response)
        except Exception:  # pragma: no cover - never break the request cycle
            logger.exception("Audit log write failed")
        return response

    def _maybe_log(self, request, response):
        method = request.method
        if method not in _AUDITED_METHODS:
            return
        path = request.path
        if any(path.startswith(p) for p in _AUDIT_EXEMPT_PREFIXES):
            return
        user = getattr(request, 'user', None)
        company = getattr(user, 'company', None) if user and user.is_authenticated else None
        AuditLogEntry.objects.create(
            company=company,
            user=user if (user and user.is_authenticated and not hasattr(user, 'api_key')) else None,
            user_email=getattr(user, 'email', '') or '',
            method=method,
            path=path[:512],
            status_code=response.status_code,
            ip=_client_ip(request),
            user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:512],
        )


class IpWhitelistMiddleware:
    """If tenant has whitelist entries AND policy.enforce_ip_whitelist=True,
    block requests from non-listed IPs."""

    EXEMPT_PREFIXES = ('/static/', '/media/', '/admin/login/', '/accounts/login/',
                       '/billing/free-fraud-audit/', '/api/v1/health/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if any(request.path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return self.get_response(request)
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return self.get_response(request)
        company = getattr(user, 'company', None)
        if company is None:
            return self.get_response(request)

        policy = CompanySecurityPolicy.for_company(company)
        if not policy or not policy.enforce_ip_whitelist:
            return self.get_response(request)
        entries = list(CompanyIpWhitelist.objects.filter(company=company, is_active=True))
        if not entries:
            return self.get_response(request)  # nothing to enforce

        ip = _client_ip(request)
        if ip and any(e.matches(ip) for e in entries):
            return self.get_response(request)

        logger.warning("[ip-whitelist] blocked %s for tenant=%s on %s", ip, company.name, request.path)
        AuditLogEntry.objects.create(
            company=company, user=user, user_email=getattr(user, 'email', '') or '',
            method=request.method, path=request.path[:512], status_code=403, ip=ip,
            user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:512],
            object_repr='IP_WHITELIST_BLOCK',
        )
        return HttpResponseForbidden(
            f"Your IP address ({ip}) is not on the allowed list for this tenant. "
            "Contact your administrator.",
        )


class DynamicSessionTimeoutMiddleware:
    """Set per-tenant session expiry on every authenticated request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and not hasattr(user, 'api_key'):
            company = getattr(user, 'company', None)
            policy = CompanySecurityPolicy.for_company(company) if company else None
            if policy:
                request.session.set_expiry(policy.session_timeout_minutes * 60)
        return self.get_response(request)
