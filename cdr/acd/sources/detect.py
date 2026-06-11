"""PBX edition / ingest-transport detection (P5.2).

Per tenant, work out which PBX family + feed is in play so the right adapter and
``ingest_transport`` tag are used. 3CX exposes its version via the XAPI
SystemStatus; absence of XAPI creds implies the socket/CSV legacy path.
"""
import logging

logger = logging.getLogger(__name__)


def parse_3cx_major(version):
    """'20.0.9.670' -> 20 ; None/'' -> None."""
    if not version:
        return None
    try:
        return int(str(version).split('.')[0])
    except (ValueError, IndexError):
        return None


def detect_pbx_edition(company, *, verify_tls=True):
    """Return a dict describing the tenant's PBX family, version and feed.

    {'source_pbx', 'edition', 'version', 'ingest_transport', 'detail'}
    Never raises — on any error it falls back to the socket assumption.
    """
    result = {
        'source_pbx': '3cx', 'edition': 'unknown', 'version': None,
        'ingest_transport': 'socket', 'detail': '',
    }
    api_url = getattr(company, 'pbx_api_url', '') or ''
    if not api_url:
        result['detail'] = 'no XAPI configured — assuming 3CX active-socket CDR'
        return result
    try:
        from acd.sources.threecx_xapi import ThreeCXXapiClient
        client = ThreeCXXapiClient(
            api_url, company.pbx_api_user, company.pbx_api_password,
            verify_tls=verify_tls, timeout=15)
        client.authenticate()
        status = client.system_status()
        version = status.get('Version')
        major = parse_3cx_major(version)
        result['version'] = version
        if major is not None and major >= 20:
            result.update(edition=f'3cx-v{major}', ingest_transport='xapi',
                          detail='3CX V20+ XAPI (cdr_output era)')
        elif major is not None:
            result.update(edition=f'3cx-v{major}-legacy', ingest_transport='socket',
                          detail='legacy 3CX (callhistory2/3) — socket/CSV path')
        else:
            result.update(edition='3cx', detail='3CX, version unparsed')
    except Exception as e:
        logger.warning('detect_pbx_edition: %s falling back to socket: %s',
                       getattr(company, 'name', '?'), e)
        result['detail'] = f'detection failed ({e}); assuming socket'
    return result
