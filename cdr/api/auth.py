"""Custom DRF authentication: API key via ``Authorization: Bearer <key>``
or ``X-API-Key: <key>`` header.

The authenticated principal is a tuple of ``(api_key.company.user-proxy, api_key)``
so that downstream views can scope querysets by ``request.user.company``
without rewriting existing logic.

Scope enforcement uses :class:`HasApiKeyScope` permission class — viewsets
declare ``required_scopes`` and the check fails if the calling key's
``scopes`` JSON list doesn't include them. An empty ``scopes`` list on a key
means "all scopes granted" (back-compat).
"""
from rest_framework import authentication, exceptions, permissions

from .models import ApiKey


class _ApiKeyUser:
    """Lightweight user-like object exposing ``.company`` for queryset filters."""

    is_authenticated = True
    is_anonymous = False
    is_active = True
    is_staff = False
    is_superuser = False

    def __init__(self, api_key: ApiKey):
        self.api_key = api_key
        self.company = api_key.company
        self.email = f"api-key/{api_key.key_prefix}@{api_key.company_id}"
        # Mirror role to match existing authorization checks
        self.role = 'api'

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):  # match Django's API
        return True

    def has_perms(self, perms, obj=None):
        return True

    def get_username(self):
        return self.email

    @property
    def pk(self):
        return self.api_key.pk

    @property
    def id(self):
        return self.api_key.pk


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """Authenticate requests via API key in Authorization or X-API-Key header."""

    keyword = 'Bearer'

    def authenticate(self, request):
        key = self._extract_key(request)
        if not key:
            return None  # let other auth classes try

        api_key = ApiKey.lookup(key)
        if api_key is None:
            raise exceptions.AuthenticationFailed('Invalid API key.')
        if api_key.is_expired():
            raise exceptions.AuthenticationFailed('API key has expired.')
        if api_key.revoked_at:
            raise exceptions.AuthenticationFailed('API key has been revoked.')

        api_key.touch()
        return (_ApiKeyUser(api_key), api_key)

    def authenticate_header(self, request):
        return f'{self.keyword} realm="api"'

    @staticmethod
    def _extract_key(request) -> str | None:
        # X-API-Key takes precedence
        x_key = request.META.get('HTTP_X_API_KEY')
        if x_key:
            return x_key.strip()
        auth = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth:
            return None
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() in ('bearer', 'apikey', 'token'):
            return parts[1].strip()
        return None


class HasApiKeyScope(permissions.BasePermission):
    """Enforce ``view.required_scopes`` against ``request.auth.scopes``.

    - Session-authenticated requests bypass this check (the user's role still
      controls UI access).
    - API keys with empty ``scopes`` list are treated as fully privileged.
    - Otherwise every required scope must appear in the key's scope list.
    """

    message = 'API key is missing one or more required scopes.'

    def has_permission(self, request, view):
        api_key = getattr(request, 'auth', None)
        # Not API-key auth → defer to other permission classes
        if api_key is None or not isinstance(api_key, ApiKey):
            return True
        required = set(getattr(view, 'required_scopes', []) or [])
        if not required:
            return True
        granted = set(api_key.scopes or [])
        if not granted:
            return True  # back-compat: empty scopes list = all permitted
        missing = required - granted
        if missing:
            self.message = (
                f"API key {api_key.key_prefix}… is missing scope(s): {sorted(missing)}"
            )
            return False
        return True
