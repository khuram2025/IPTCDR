"""3CX V20 XAPI client — queue-performance source for real ACD KPIs.

The 3CX active-socket CDR feed cannot supply agent-wait timing (time_answered is
the IVR auto-answer instant). The XAPI report endpoint
``ReportDetailedQueueStatistics`` does — it returns real per-queue CallsCount /
AnsweredCount / RingTime (= speed of answer) / TalkTime. This client authenticates
against a tenant's 3CX, lists its queues, and pulls those stats.

Pure ``requests`` — no Django imports — so it can be unit-tested standalone.
Direct Postgres to the 3CX host is firewalled (:5432), so XAPI is the path.
"""
import re
import logging

import requests

logger = logging.getLogger(__name__)

# ISO-8601 duration like PT31.015254S / PT2M1.4S / PT5H4M59S / P30D / P21DT14H28M28S.
# The time portion (T...) is optional so day-only durations (LoggedInTime='P30D') parse.
_ISO_DUR = re.compile(
    r'P(?:(?P<d>\d+)D)?(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>[\d.]+)S)?)?'
)


def iso_duration_to_seconds(value):
    """'PT2M1.4S' -> 121.4 (float seconds). None/'' -> None."""
    if not value:
        return None
    m = _ISO_DUR.fullmatch(value.strip())
    if not m:
        return None
    d = int(m.group('d') or 0)
    h = int(m.group('h') or 0)
    mins = int(m.group('m') or 0)
    s = float(m.group('s') or 0)
    return d * 86400 + h * 3600 + mins * 60 + s


def _iso(dt):
    """datetime -> '2026-06-01T00:00:00Z' (UTC, no offset)."""
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


class ThreeCXXapiError(Exception):
    pass


class ThreeCXXapiClient:
    """Minimal authenticated client for the 3CX V20 XAPI reporting endpoints."""

    def __init__(self, base_url, username, password, *, verify_tls=True, timeout=40):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.timeout = timeout
        self._token = None

    # -- auth -----------------------------------------------------------------
    def authenticate(self):
        url = f'{self.base_url}/webclient/api/Login/GetAccessToken'
        resp = requests.post(
            url,
            json={'SecurityCode': '', 'Username': self.username, 'Password': self.password},
            headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
            verify=self.verify_tls, timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise ThreeCXXapiError(f'auth HTTP {resp.status_code}: {resp.text[:200]}')
        token = (resp.json() or {}).get('Token', {}).get('access_token')
        if not token:
            raise ThreeCXXapiError('auth succeeded but no access_token in response')
        self._token = token
        return token

    def _get(self, path):
        if not self._token:
            self.authenticate()
        url = f'{self.base_url}{path}'
        resp = requests.get(
            url, headers={'Authorization': f'Bearer {self._token}'},
            verify=self.verify_tls, timeout=self.timeout,
        )
        if resp.status_code == 401:  # token expired — refresh once
            self.authenticate()
            resp = requests.get(
                url, headers={'Authorization': f'Bearer {self._token}'},
                verify=self.verify_tls, timeout=self.timeout,
            )
        if resp.status_code != 200:
            raise ThreeCXXapiError(f'GET {path[:80]} -> HTTP {resp.status_code}: {resp.text[:200]}')
        return resp.json()

    # -- reads ----------------------------------------------------------------
    def system_status(self):
        return self._get('/xapi/v1/SystemStatus')

    def active_calls(self):
        """Live snapshot of calls currently up on the PBX (the wallboard feed).

        Returns a list of dicts: id, caller, callee, status (Talking / Routing /
        Ringing / ...), established_at, last_change, server_now. ServerNow is the
        PBX clock at read time — use it (not the app clock) to age each call so the
        wait math is immune to host/PBX clock skew. Capped at 100 by the endpoint.
        """
        data = self._get('/xapi/v1/ActiveCalls?%24top=100')
        out = []
        for r in data.get('value', []):
            out.append({
                'id': r.get('Id'),
                'caller': r.get('Caller') or '',
                'callee': r.get('Callee') or '',
                'status': r.get('Status') or '',
                'established_at': r.get('EstablishedAt'),
                'last_change': r.get('LastChangeStatus'),
                'server_now': r.get('ServerNow'),
            })
        return out

    def list_queues(self):
        """[(number, name), ...] of the tenant's real ACD queues."""
        data = self._get('/xapi/v1/Queues?%24select=Number,Name')
        return [(q.get('Number'), q.get('Name')) for q in data.get('value', []) if q.get('Number')]

    def list_users(self, page_size=100):
        """All provisioned user extensions (the REAL users -- queues/IVRs/ring
        groups are separate XAPI object types and are not returned here).

        The endpoint caps $top at 100, so we page with $skip. Returns dicts:
        pbx_id, number, first_name, last_name, display_name, email, mobile,
        outbound_caller_id, enabled, is_registered, internal.
        """
        select = (
            'Id,Number,FirstName,LastName,DisplayName,EmailAddress,Mobile,'
            'OutboundCallerID,Enabled,IsRegistered,Internal'
        )
        out, skip = [], 0
        while True:
            data = self._get(
                f'/xapi/v1/Users?%24select={select}&%24top={page_size}&%24skip={skip}'
            )
            batch = data.get('value', [])
            for u in batch:
                number = (u.get('Number') or '').strip()
                if not number:
                    continue
                out.append({
                    'pbx_id': u.get('Id'),
                    'number': number,
                    'first_name': (u.get('FirstName') or '').strip(),
                    'last_name': (u.get('LastName') or '').strip(),
                    'display_name': (u.get('DisplayName') or '').strip(),
                    'email': (u.get('EmailAddress') or '').strip(),
                    'mobile': (u.get('Mobile') or '').strip(),
                    'outbound_caller_id': (u.get('OutboundCallerID') or '').strip(),
                    'enabled': bool(u.get('Enabled')),
                    'is_registered': bool(u.get('IsRegistered')),
                    'internal': bool(u.get('Internal')),
                })
            if len(batch) < page_size:
                break
            skip += page_size
            if skip > 100000:  # safety backstop against an endless loop
                break
        return out

    def detailed_queue_statistics(self, queue_dns, start, end, wait_interval='00:00:00'):
        """Per-queue aggregate stats for [start, end].

        queue_dns: iterable of queue DN strings. The 3CX endpoint only honours a
        SINGLE DN in queueDnStr (comma/semicolon lists silently return nothing),
        so we query one queue at a time and combine. Returns list of dicts with
        seconds already parsed: calls, answered, avg_ring_seconds (ASA),
        avg_talk_seconds, ring_time_seconds, talk_time_seconds, callbacks.
        """
        out = []
        for dn in queue_dns:
            dn = str(dn).strip()
            if not dn:
                continue
            path = (
                "/xapi/v1/ReportDetailedQueueStatistics/Pbx.GetDetailedQueueStatisticsData("
                f"queueDnStr='{dn}',startDt={_iso(start)},endDt={_iso(end)},"
                f"waitInterval='{wait_interval}')"
            )
            for row in self._get(path).get('value', []):
                out.append({
                    'queue_dn': (row.get('QueueDnNumber') or dn).strip(),
                    'queue_label': row.get('QueueDn') or '',
                    'calls': row.get('CallsCount') or 0,
                    'answered': row.get('AnsweredCount') or 0,
                    'ring_time_seconds': iso_duration_to_seconds(row.get('RingTime')),
                    'avg_ring_seconds': iso_duration_to_seconds(row.get('AvgRingTime')),
                    'talk_time_seconds': iso_duration_to_seconds(row.get('TalkTime')),
                    'avg_talk_seconds': iso_duration_to_seconds(row.get('AvgTalkTime')),
                    'callbacks': row.get('CallbacksCount') or 0,
                })
        return out

    def abandoned_queue_calls(self, queue_dns, start, end, wait_interval='00:00:00'):
        """Per-call ABANDONED records (caller hung up before an agent answered).

        The socket CDR cannot tell a real abandon from an IVR hangup; this report
        can, and crucially carries WaitTime — how long the caller actually waited
        before giving up (the true patience / lost-opportunity metric). One DN at a
        time (same single-DN constraint as detailed_queue_statistics). Returns a
        list of dicts: queue_dn, external_id (CallHistoryId, stable per call),
        call_time (ISO str, tz-aware), wait_seconds, caller_id, agent_dn (the ext it
        was ringing when abandoned), agent_name, polling_attempts, was_logged_in.
        """
        out = []
        for dn in queue_dns:
            dn = str(dn).strip()
            if not dn:
                continue
            path = (
                "/xapi/v1/ReportAbandonedQueueCalls/Pbx.GetAbandonedQueueCallsData("
                f"periodFrom={_iso(start)},periodTo={_iso(end)},"
                f"queueDns='{dn}',waitInterval='{wait_interval}')"
            )
            for row in self._get(path).get('value', []):
                out.append({
                    'queue_dn': (row.get('QueueDn') or dn).strip(),
                    'queue_label': row.get('QueueDisplayName') or '',
                    'external_id': (row.get('CallHistoryId') or '').strip(),
                    'call_time': row.get('CallTime'),
                    'wait_seconds': iso_duration_to_seconds(row.get('WaitTime')),
                    'caller_id': (row.get('CallerId') or '')[:64],
                    'agent_dn': (row.get('ExtensionDn') or '')[:32],
                    'agent_name': (row.get('ExtensionDisplayName') or '')[:128],
                    'polling_attempts': row.get('PollingAttempts') or 0,
                    'was_logged_in': bool(row.get('IsLoggedIn')),
                })
        return out

    def agents_in_queue_statistics(self, queue_dns, start, end, wait_interval='00:00:00'):
        """Per-agent productivity WITHIN each queue for [start, end].

        Gives the agent-side picture the socket CDR can't: LoggedInTime (for
        occupancy = talk / logged-in), AnsweredCount, LostCount (rings that went
        unanswered by this agent), AnsweredPercent, and real Ring/Talk timing. One
        DN at a time. Returns dicts: queue_dn, agent_dn, agent_name, answered, lost,
        answered_pct, logged_in_seconds, ring_time_seconds, avg_ring_seconds,
        talk_time_seconds, avg_talk_seconds.
        """
        out = []
        for dn in queue_dns:
            dn = str(dn).strip()
            if not dn:
                continue
            path = (
                "/xapi/v1/ReportAgentsInQueueStatistics/Pbx.GetAgentsInQueueStatisticsData("
                f"queueDnStr='{dn}',startDt={_iso(start)},endDt={_iso(end)},"
                f"waitInterval='{wait_interval}')"
            )
            for row in self._get(path).get('value', []):
                out.append({
                    'queue_dn': (row.get('Queue') or dn).strip(),
                    'agent_dn': (row.get('Dn') or '').strip()[:32],
                    'agent_name': (row.get('DnDisplayName') or '')[:128],
                    'answered': row.get('AnsweredCount') or 0,
                    'lost': row.get('LostCount') or 0,
                    'answered_pct': row.get('AnsweredPercent') or 0,
                    'logged_in_seconds': iso_duration_to_seconds(row.get('LoggedInTime')),
                    'ring_time_seconds': iso_duration_to_seconds(row.get('RingTime')),
                    'avg_ring_seconds': iso_duration_to_seconds(row.get('AvgRingTime')),
                    'talk_time_seconds': iso_duration_to_seconds(row.get('TalkTime')),
                    'avg_talk_seconds': iso_duration_to_seconds(row.get('AvgTalkTime')),
                })
        return out
