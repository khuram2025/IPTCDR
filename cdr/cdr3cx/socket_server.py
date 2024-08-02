import socket
import threading
import os
import django
import sys
import logging
from django.utils import timezone
from django.utils.dateparse import parse_datetime

# Set up Django environment
sys.path.append('/home/ubuntu/3CX/cdr')  # Path to your Django project
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cdr.settings')
django.setup()

from cdr3cx.models import CallRecord  # Use absolute import for the model

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handle_client_connection(client_socket):
    try:
        request = client_socket.recv(1024).decode('utf-8').strip()
        logger.info(f"Received data: {request}")

        # # Save raw data to a file for debugging
        # records_file_path = os.path.join('/home/ubuntu/3CX/cdr', 'records.txt')
        # with open(records_file_path, 'a') as f:
        #     f.write(f"{request}\n")

        # Remove 'Call ' prefix if present
        if request.startswith('Call '):
            request = request[5:]

        # Split the data
        cdr_data = request.split(',')
        logger.info(f"Parsed CDR data: {cdr_data}")

        if len(cdr_data) < 3:
            logger.error("Insufficient data fields")
            client_socket.send(b"Error: Insufficient data")
            client_socket.close()
            return

        # Extract and parse the data
        call_time_str = cdr_data[0].strip().replace('/', '-')
        callee = cdr_data[1].strip()
        caller = cdr_data[2].strip()
        duration_str = cdr_data[3].strip()
        time_answered_str = cdr_data[4].strip().replace('/', '-')
        time_end_str = cdr_data[5].strip().replace('/', '-')
        reason_terminated = cdr_data[6].strip()
        reason_changed = cdr_data[7].strip() if len(cdr_data) > 7 else ''
        missed_queue_calls = cdr_data[8].strip() if len(cdr_data) > 8 else ''
        from_no = cdr_data[9].strip() if len(cdr_data) > 9 else ''
        to_no = cdr_data[10].strip() if len(cdr_data) > 10 else ''
        to_dn = cdr_data[11].strip() if len(cdr_data) > 11 else ''
        final_number = cdr_data[12].strip() if len(cdr_data) > 12 else ''
        final_dn = cdr_data[13].strip() if len(cdr_data) > 13 else ''
        from_type = cdr_data[14].strip() if len(cdr_data) > 14 else ''
        to_type = cdr_data[15].strip() if len(cdr_data) > 15 else ''
        final_type = cdr_data[16].strip() if len(cdr_data) > 16 else ''
        from_dispname = cdr_data[17].strip() if len(cdr_data) > 17 else ''
        to_dispname = cdr_data[18].strip() if len(cdr_data) > 18 else ''
        final_dispname = cdr_data[19].strip() if len(cdr_data) > 19 else ''

        # Parse the datetime fields and make them timezone-aware
        try:
            call_time = timezone.make_aware(parse_datetime(call_time_str), timezone.get_current_timezone()) if call_time_str else None
            time_answered = timezone.make_aware(parse_datetime(time_answered_str), timezone.get_current_timezone()) if time_answered_str else None
            time_end = timezone.make_aware(parse_datetime(time_end_str), timezone.get_current_timezone()) if time_end_str else None
            if call_time is None:
                raise ValueError(f"Failed to parse datetime from string: {call_time_str}")
        except Exception as e:
            logger.error(f"Error parsing datetime: {e}")
            client_socket.send(f"Error parsing datetime: {e}".encode('utf-8'))
            client_socket.close()
            return

        # Convert duration to seconds if available
        try:
            if duration_str:
                duration_parts = duration_str.split(':')
                duration = int(duration_parts[0]) * 3600 + int(duration_parts[1]) * 60 + int(duration_parts[2])
            else:
                duration = None
        except Exception as e:
            logger.error(f"Error parsing duration: {e}")
            duration = None

        # Save to database
        try:
            call_record = CallRecord.objects.create(
                caller=caller,
                callee=callee,
                call_time=call_time,
                external_number=callee,
                duration=duration,
                time_answered=time_answered,
                time_end=time_end,
                reason_terminated=reason_terminated,
                reason_changed=reason_changed,
                missed_queue_calls=missed_queue_calls,
                from_no=from_no,
                to_no=to_no,
                to_dn=to_dn,
                final_number=final_number,
                final_dn=final_dn,
                from_type=from_type,
                to_type=to_type,
                final_type=final_type,
                from_dispname=from_dispname,
                to_dispname=to_dispname,
                final_dispname=final_dispname
            )
            logger.info(f"Saved call record: {call_record}")
            client_socket.send(b"CDR received and processed")
        except Exception as e:
            logger.error(f"Error saving call record: {e}")
            print(f"Error saving call record: {e}")
            client_socket.send(f"Error processing CDR: {e}".encode('utf-8'))

    except Exception as e:
        logger.error(f"Error handling client connection: {e}")
        print(f"Error handling client connection: {e}")
    finally:
        client_socket.close()

# Main function to set up the server
def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Add this line
    server.bind(('0.0.0.0', 8000))
    server.listen(5)  # max backlog of connections

    logger.info("Listening on port 8000")

    while True:
        client_sock, address = server.accept()
        logger.info(f"Accepted connection from {address}")
        client_handler = threading.Thread(
            target=handle_client_connection,
            args=(client_sock,)  # pass client socket object
        )
        client_handler.start()

if __name__ == '__main__':
    main()
