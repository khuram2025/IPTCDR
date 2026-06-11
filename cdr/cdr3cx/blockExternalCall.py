"""Toggle an extension's external-calling permission on its 3CX (XAPI).

Credentials are ALWAYS tenant-specific and supplied by the caller from the owning
Company's ``pbx_api_url`` / ``pbx_api_user`` / ``pbx_api_password`` -- there is no
hardcoded PBX or password in this module. Pure ``requests`` (no Django imports) so
it stays unit-testable; callers resolve the company creds and pass them in.
"""
import logging

import requests
import urllib3

# 3CX commonly uses self-signed certs on the management port; callers can still
# force verification via verify_tls=True (default), which works for tenants with
# valid certs (same path the XAPI reporting client uses).
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

TIMEOUT = 30


def _domain_from_base_url(base_url):
    """'https://pbx.example.com:5001' -> 'pbx.example.com:5001'. '' if blank."""
    if not base_url:
        return ''
    return base_url.replace('https://', '').replace('http://', '').rstrip('/')


def authenticate_user(domain, user, password, verify_tls=True):
    """Return a 3CX access token for these creds, or None on any failure."""
    if not (domain and user and password):
        logger.warning('authenticate_user: missing PBX domain/user/password')
        return None
    url = f'https://{domain}/webclient/api/Login/GetAccessToken'
    try:
        response = requests.post(
            url,
            headers={'Accept': 'application/json', 'Content-Type': 'application/json'},
            json={'SecurityCode': '', 'Password': password, 'Username': user},
            verify=verify_tls, timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        logger.warning('authenticate_user: request error: %s', e)
        return None
    if response.status_code != 200:
        logger.warning('authenticate_user: HTTP %s', response.status_code)
        return None
    data = response.json() or {}
    if data.get('Status') == 'AuthSuccess':
        return (data.get('Token') or {}).get('access_token')
    logger.warning('authenticate_user: auth failed (Status=%s)', data.get('Status'))
    return None


def get_user_id(access_token, extension_number, domain, verify_tls=True):
    """Resolve the 3CX Users.Id for an extension number, or None."""
    url = f'https://{domain}/xapi/v1/Users'
    try:
        response = requests.get(
            url,
            headers={'Authorization': f'Bearer {access_token}'},
            params={'$filter': f"Number eq '{extension_number}'"},
            verify=verify_tls, timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        logger.warning('get_user_id: request error: %s', e)
        return None
    if response.status_code != 200:
        logger.warning('get_user_id: HTTP %s', response.status_code)
        return None
    values = (response.json() or {}).get('value') or []
    if not values:
        logger.warning('get_user_id: extension %s not found on PBX', extension_number)
        return None
    return values[0].get('Id')


def set_external_call(extension_number, allow_external, base_url=None, user=None,
                      password=None, verify_tls=True):
    """Set an extension's external-calling permission on its 3CX.

    allow_external=True  -> Internal=False (external calls allowed)
    allow_external=False -> Internal=True  (external calls blocked)

    base_url/user/password are REQUIRED (the owning Company's pbx_api_*); without
    a full set this returns False (no hardcoded fallback). Returns True on success.
    """
    domain = _domain_from_base_url(base_url)
    if not (domain and user and password):
        logger.warning(
            'set_external_call: missing PBX credentials for ext %s; skipping',
            extension_number)
        return False

    access_token = authenticate_user(domain, user, password, verify_tls=verify_tls)
    if not access_token:
        return False

    user_id = get_user_id(access_token, extension_number, domain, verify_tls=verify_tls)
    if not user_id:
        return False

    url = f'https://{domain}/xapi/v1/Users({user_id})'
    try:
        response = requests.patch(
            url,
            headers={'Authorization': f'Bearer {access_token}',
                     'Content-Type': 'application/json'},
            json={'Internal': not allow_external},
            verify=verify_tls, timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        logger.warning('set_external_call: request error: %s', e)
        return False

    if response.status_code in (200, 204):
        logger.info('set_external_call: ext %s -> external calls %s',
                    extension_number, 'ALLOWED' if allow_external else 'BLOCKED')
        return True
    logger.warning('set_external_call: PATCH HTTP %s for ext %s: %s',
                   response.status_code, extension_number, response.text[:200])
    return False
