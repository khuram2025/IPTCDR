import socket
import ipaddress
import threading
import time
import os
import django
import sys
import logging
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db.models import Q

# Set up Django environment
sys.path.append('/home/ubuntu/3CX/cdr')  # Path to your Django project
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cdr.settings')
django.setup()

from django.db import close_old_connections
from cdr3cx.models import CallRecord, Company  # Use absolute import for the models

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# How often (seconds) to re-scan the Company table for added/removed ports.
# A company created from the UI starts receiving CDRs within this window,
# with no service restart required.
PORT_REFRESH_INTERVAL = 5

# Registry of currently-running listeners: port -> threading.Event used to stop it.
_active_lock = threading.Lock()
_active_listeners = {}


def normalize_cdr_token(value):
    """Canonicalize 3CX type/reason tokens at ingest to prevent case drift."""
    if value is None:
        return value
    cleaned = value.strip()
    return cleaned.lower() if cleaned else cleaned


def recv_all(client_socket, chunk_size=4096):
    """Read until the PBX closes the connection (fixes single recv(1024) truncation)."""
    chunks = []
    while True:
        chunk = client_socket.recv(chunk_size)
        if not chunk:
            break
        chunks.append(chunk)
    return b''.join(chunks).decode('utf-8', errors='replace').strip()


def is_ip_allowed(ip_address, company):
    """Per-tenant CDR-source allowlist, configured from the company UI.

    company.pbx_source_ips is a comma-separated list of IPs/CIDRs that may send
    CDRs to this company's listening port. Blank => allow any source (so a
    tenant that has not configured a PBX IP yet is never cut off).
    """
    raw = (getattr(company, 'pbx_source_ips', '') or '').strip()
    if not raw:
        return True
    try:
        client = ipaddress.ip_address(ip_address)
    except ValueError:
        return False
    for token in raw.split(','):
        token = token.strip()
        if not token:
            continue
        try:
            if client in ipaddress.ip_network(token, strict=False):
                return True
        except ValueError:
            logger.warning(f"Invalid pbx_source_ips entry '{token}' for company {company.name}")
    return False

def get_company_for_port(port):
    try:
        return Company.objects.get(listening_port=port)
    except Company.DoesNotExist:
        logger.warning(f"No company found for port {port}. Using default company.")
        return Company.objects.get_or_create(name="Default Company")[0]


# ---------------------------------------------------------------------------
# 3CX CDR field layouts. The active-socket feed is POSITIONAL: each PBX sends a
# comma-separated record whose column order is whatever its "CDR output fields"
# page is set to. All tenants are being standardized onto CDR_FIELDS_CANONICAL
# (historyid first, time-start at index 3). Some PBXs may still emit the legacy
# layout (time-start at index 0) during the cutover, so we auto-detect and parse
# either one, mapping both to the same field names. No CDR is lost mid-migration.
# ---------------------------------------------------------------------------

# Canonical layout -- configure EVERY PBX's CDR output fields in this exact order.
CDR_FIELDS_CANONICAL = [
    'historyid', 'callid', 'duration', 'time-start', 'time-answered',
    'time-end', 'reason-terminated', 'from-no', 'to-no', 'from-dn', 'to-dn',
    'dial-no', 'reason-changed', 'final-number', 'final-dn', 'bill-code',
    'bill-rate', 'bill-cost', 'bill-name', 'chain', 'from-type', 'to-type',
    'final-type', 'from-dispname', 'to-dispname', 'final-dispname',
    'missed-queue-calls',
]

# Legacy layout still emitted by not-yet-migrated PBXs (no historyid/callid/
# billing columns; time-start first). Retained only for a seamless transition.
CDR_FIELDS_LEGACY = [
    'time-start', 'dial-no', 'from-dn', 'duration', 'time-answered',
    'time-end', 'reason-terminated', 'reason-changed', 'missed-queue-calls',
    'from-no', 'to-no', 'to-dn', 'final-number', 'final-dn', 'from-type',
    'to-type', 'final-type', 'from-dispname', 'to-dispname', 'final-dispname',
]


def _looks_like_datetime(value):
    """True if value parses as a 3CX timestamp (YYYY/MM/DD HH:MM:SS)."""
    if not value:
        return False
    return parse_datetime(value.strip().replace('/', '-')) is not None


def parse_cdr_fields(cdr_data):
    """Map a comma-split 3CX CDR record to a {field-name: value} dict.

    Layout is detected from position 0: a timestamp there means the legacy
    layout (time-start first); anything else means the canonical layout
    (historyid first). Returns (fields, layout_name). Trailing fields that the
    PBX omitted default to ''.
    """
    layout = CDR_FIELDS_LEGACY if _looks_like_datetime(cdr_data[0]) else CDR_FIELDS_CANONICAL
    fields = {
        name: (cdr_data[i].strip() if i < len(cdr_data) else '')
        for i, name in enumerate(layout)
    }
    return fields, ('legacy' if layout is CDR_FIELDS_LEGACY else 'canonical')


# Drop a persistent PBX connection after this many idle seconds (it reconnects).
SOCKET_IDLE_TIMEOUT = 3600


def process_cdr_record(request, port):
    """Parse one 3CX CDR record and persist it. No socket I/O -- the caller owns
    the (possibly persistent) connection -- so this is safe to call once per
    record streamed over an open connection."""
    request = request.strip()
    if not request:
        return

    try:
        with open('/home/ubuntu/3CX/cdr/debug.log', 'a') as debug_file:
            debug_file.write(f"[{timezone.now()}] Raw message on port {port}: {request}\n")
    except Exception:
        pass

    if request.startswith('Call '):
        request = request[5:]

    cdr_data = request.split(',')
    if len(cdr_data) < 3:
        logger.error(f"Insufficient data fields on port {port}: {request[:80]!r}")
        return

    # Map positional fields to names by auto-detecting the PBX's CDR layout.
    fields, cdr_format = parse_cdr_fields(cdr_data)

    # Preserve the established semantics: caller = from-dn, callee = dial-no.
    call_time_str = fields['time-start'].replace('/', '-')
    callee = fields['dial-no']
    caller = fields['from-dn']
    duration_str = fields['duration']
    time_answered_str = fields['time-answered'].replace('/', '-')
    time_end_str = fields['time-end'].replace('/', '-')
    reason_terminated = fields['reason-terminated']
    reason_changed = fields['reason-changed']
    missed_queue_calls = fields['missed-queue-calls']
    from_no = fields['from-no']
    to_no = fields['to-no']
    to_dn = fields['to-dn']
    final_number = fields['final-number']
    final_dn = fields['final-dn']
    from_type = fields['from-type']
    to_type = fields['to-type']
    final_type = fields['final-type']
    from_dispname = fields['from-dispname']
    to_dispname = fields['to-dispname']
    final_dispname = fields['final-dispname']
    historyid = fields.get('historyid', '')
    callid = fields.get('callid', '')

    try:
        call_time = timezone.make_aware(parse_datetime(call_time_str), timezone.get_current_timezone()) if call_time_str else None
        time_answered = timezone.make_aware(parse_datetime(time_answered_str), timezone.get_current_timezone()) if time_answered_str else None
        time_end = timezone.make_aware(parse_datetime(time_end_str), timezone.get_current_timezone()) if time_end_str else None
        if call_time is None:
            raise ValueError(f"Failed to parse datetime from string: {call_time_str}")
    except Exception as e:
        logger.error(f"Error parsing datetime on port {port}: {e}")
        return

    try:
        if duration_str:
            duration_parts = duration_str.split(':')
            duration = int(duration_parts[0]) * 3600 + int(duration_parts[1]) * 60 + int(duration_parts[2])
        else:
            duration = None
    except Exception as e:
        logger.error(f"Error parsing duration on port {port}: {e}")
        duration = None

    company = get_company_for_port(port)

    try:
        call_record = CallRecord.objects.create(
            company=company,
            caller=caller,
            callee=callee,
            call_time=call_time,
            external_number=callee,
            duration=duration,
            time_answered=time_answered,
            time_end=time_end,
            reason_terminated=normalize_cdr_token(reason_terminated),
            reason_changed=reason_changed,
            missed_queue_calls=missed_queue_calls,
            from_no=from_no,
            to_no=to_no,
            to_dn=to_dn,
            final_number=final_number,
            final_dn=final_dn,
            from_type=normalize_cdr_token(from_type),
            to_type=normalize_cdr_token(to_type),
            final_type=normalize_cdr_token(final_type),
            from_dispname=from_dispname,
            to_dispname=to_dispname,
            final_dispname=final_dispname,
            external_id=historyid or None,
            correlation_id=callid or None,
            raw_data={**fields, 'cdr_format': cdr_format, 'source_port': port},
        )
        logger.info(f"Saved call record for company {company.name}: {call_record}")
    except Exception as e:
        logger.error(f"Error saving call record on port {port}: {e}")


def handle_client_connection(client_socket, port):
    """Consume CDR records from a 3CX active socket.

    3CX terminates each record with CRLF and MAY keep the connection open and
    stream many CDRs over it (persistent mode). We read continuously and process
    each complete newline-terminated record as it arrives -- instead of waiting
    for the connection to close -- while still handling the per-connection case
    (one record then close) by flushing any trailing unterminated record on
    disconnect. Replaces the old recv_all() which blocked forever on a persistent
    stream and therefore never saved its CDRs.
    """
    try:
        client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except OSError:
        pass
    client_socket.settimeout(SOCKET_IDLE_TIMEOUT)

    buffer = ''
    try:
        while True:
            try:
                chunk = client_socket.recv(8192)
            except socket.timeout:
                logger.info(f"Idle timeout on port {port}; closing connection")
                break
            except OSError as e:
                logger.warning(f"Socket error on port {port}: {e}")
                break
            if not chunk:
                break  # peer closed the connection
            buffer += chunk.decode('utf-8', errors='replace')
            while True:
                nl = buffer.find('\n')
                if nl == -1:
                    break
                line = buffer[:nl]
                buffer = buffer[nl + 1:]
                process_cdr_record(line, port)
    except Exception as e:
        logger.error(f"Error handling client connection on port {port}: {e}")
    finally:
        leftover = buffer.strip()
        if leftover:
            try:
                process_cdr_record(leftover, port)
            except Exception as e:
                logger.error(f"Error processing final record on port {port}: {e}")
        try:
            client_socket.close()
        except OSError:
            pass

def start_server(port, stop_event):
    """Listen on `port` until `stop_event` is set.

    Uses a short accept timeout so the loop can notice stop_event (set when a
    company's port is removed/changed) and shut the socket down cleanly.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(('0.0.0.0', port))
        server.listen(5)  # max backlog of connections
    except OSError as e:
        logger.error(f"Could not bind port {port}: {e}")
        server.close()
        # Drop from registry so the reconcile loop retries on its next pass.
        with _active_lock:
            if _active_listeners.get(port) is stop_event:
                del _active_listeners[port]
        return

    server.settimeout(1.0)
    logger.info(f"Listening on port {port}")

    while not stop_event.is_set():
        try:
            client_sock, address = server.accept()
        except socket.timeout:
            continue
        except OSError as e:
            if stop_event.is_set():
                break
            logger.error(f"Accept error on port {port}: {e}")
            continue

        client_ip = address[0]
        # Long-lived thread: drop any DB connection that the server closed while idle.
        close_old_connections()
        company = get_company_for_port(port)
        if not is_ip_allowed(client_ip, company):
            logger.warning(f"Rejected connection from {client_ip} on port {port}")
            client_sock.close()
            continue
        logger.info(f"Accepted connection from {address} on port {port}")
        client_handler = threading.Thread(
            target=handle_client_connection,
            args=(client_sock, port)
        )
        client_handler.start()

    server.close()
    logger.info(f"Stopped listening on port {port}")


def get_configured_ports():
    """Current set of company listening ports, falling back to 8000 if none set."""
    ports = set(
        Company.objects.exclude(listening_port__isnull=True)
        .values_list('listening_port', flat=True)
        .distinct()
    )
    if not ports:
        logger.warning("No ports configured in Company model. Using default port 8000.")
        ports = {8000}
    return ports


def reconcile_listeners():
    """Sync running listeners with the Company table.

    Starts a listener for every newly-added company port and stops listeners
    whose company/port was removed. Lets a company created in the UI begin
    receiving CDRs within PORT_REFRESH_INTERVAL seconds, with no restart.
    """
    # Fresh DB connection each pass so a dropped connection never wedges the loop.
    close_old_connections()
    try:
        desired = get_configured_ports()
    except Exception as e:
        logger.error(f"Could not read configured ports: {e}")
        return

    with _active_lock:
        running = set(_active_listeners.keys())

        for port in desired - running:
            stop_event = threading.Event()
            _active_listeners[port] = stop_event
            thread = threading.Thread(
                target=start_server, args=(port, stop_event), daemon=True
            )
            thread.start()
            logger.info(f"Started listener for new port {port}")

        for port in running - desired:
            logger.info(f"Stopping listener for removed port {port}")
            _active_listeners[port].set()
            del _active_listeners[port]


# Main function to set up the server
def main():
    logger.info("Socket server starting; entering port-reconciliation loop.")
    while True:
        reconcile_listeners()
        time.sleep(PORT_REFRESH_INTERVAL)

if __name__ == '__main__':
    main()
