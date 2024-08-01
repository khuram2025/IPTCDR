import socket
import threading
import os
import django
import sys
import logging

# Set up Django environment
sys.path.append('/home/ubuntu/3CX/cdr')  # Path to your Django project
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cdr.settings')
django.setup()

from cdr3cx.models import CallRecord  # Use absolute import for the model
from django.utils.dateparse import parse_datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handle_client_connection(client_socket):
    try:
        request = client_socket.recv(1024).decode('utf-8').strip()
        logger.info(f"Received data: {request}")

        # Save raw data to a file for debugging
        records_file_path = os.path.join('/home/ubuntu/3CX/cdr', 'records.txt')
        with open(records_file_path, 'a') as f:
            f.write(f"{request}\n")

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
        call_time_str, callee, caller = cdr_data[0].strip(), cdr_data[1].strip(), cdr_data[2].strip()
        call_time_str = call_time_str.replace('/', '-')  # Replace / with - to match ISO format

        # Parse the date and time
        try:
            call_time = parse_datetime(call_time_str)
            if call_time is None:
                raise ValueError(f"Failed to parse datetime from string: {call_time_str}")
        except Exception as e:
            logger.error(f"Error parsing call time: {e}")
            client_socket.send(f"Error parsing call time: {e}".encode('utf-8'))
            client_socket.close()
            return

        # Save to database
        try:
            call_record = CallRecord.objects.create(
                caller=caller,
                callee=callee,
                call_time=call_time,
                external_number=callee  # Assuming external_number is the same as callee
            )
            logger.info(f"Saved call record: {call_record}")
            client_socket.send(b"CDR received and processed")
        except Exception as e:
            logger.error(f"Error saving call record: {e}")
            client_socket.send(f"Error processing CDR: {e}".encode('utf-8'))

    except Exception as e:
        logger.error(f"Error handling client connection: {e}")
    finally:
        client_socket.close()

# Main function to set up the server
def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Add this line
    server.bind(('0.0.0.0', 8003))
    server.listen(5)  # max backlog of connections

    logger.info("Listening on port 8003")

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
