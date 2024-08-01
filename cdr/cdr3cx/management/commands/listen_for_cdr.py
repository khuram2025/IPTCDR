# In a new file: management/commands/cdr_listener.py

import socket
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from cdr3cx.models import CallRecord  # Adjust the import path as needed
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Starts a socket server to listen for 3CX CDR data'

    def handle(self, *args, **options):
        host = '0.0.0.0'  # Listen on all available interfaces
        port = 8000  # Use the same port as your Django development server

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            s.listen()
            self.stdout.write(self.style.SUCCESS(f'Listening for CDR data on {host}:{port}'))
            
            while True:
                conn, addr = s.accept()
                with conn:
                    self.stdout.write(f'Connected by {addr}')
                    data = conn.recv(1024).decode('utf-8')
                    self.process_cdr(data)
                    conn.sendall(b'CDR received and processed')

    def process_cdr(self, raw_data):
        logger.info(f"Received raw data: {raw_data}")

        # Remove 'Call ' prefix if present
        if raw_data.startswith('Call '):
            raw_data = raw_data[5:]

        # Split the data
        cdr_data = raw_data.split(',')
        logger.info(f"Parsed CDR data: {cdr_data}")

        if len(cdr_data) < 3:
            logger.error("Insufficient data fields")
            return

        # Extract and parse the data
        call_time_str, callee, caller = cdr_data
        call_time = parse_datetime(f"2024-07-26 {call_time_str}")

        # Save to database
        try:
            call_record = CallRecord.objects.create(
                caller=caller,
                callee=callee,
                call_time=call_time,
                external_number=callee  # Assuming external_number is the same as callee
            )
            logger.info(f"Saved call record: {call_record}")
        except Exception as e:
            logger.error(f"Error saving call record: {e}")