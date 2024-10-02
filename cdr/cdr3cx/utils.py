import logging


logger = logging.getLogger(__name__)
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import re
from .project_numbers import COUNTRY_CODES
from django.utils import timezone
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta

def get_country_from_number(number):
    logger.info(f"Original number: {number}")
    # Remove any non-digit characters from the number
    cleaned_number = re.sub(r'\D', '', number)
    logger.info(f"Cleaned number: {cleaned_number}")
    
    # Internal company call (4 digits)
    if len(cleaned_number) == 4:
        return 'Internal Company Call'
    
    # Saudi Arabia mobile number (10 digits starting with 05)
    if len(cleaned_number) == 10 and cleaned_number.startswith('05'):
        return 'Saudi Arabia Mobile'
    
    # Handle Saudi Arabia numbers with international prefixes (+966 or 00966)
    if cleaned_number.startswith('00966'):
        cleaned_number = cleaned_number[5:]  # Remove '00966'
    elif cleaned_number.startswith('966') and len(cleaned_number) > 9:
        cleaned_number = cleaned_number[3:]  # Remove '966' when prefixed by '+'
    
    if len(cleaned_number) == 9 and cleaned_number.startswith('5'):
        return 'Saudi Arabia Mobile'
    
    # Saudi Arabia landline (9 digits starting with 01, 02, 03, 04, 06, 07)
    if len(cleaned_number) == 9 and cleaned_number[0] == '0' and cleaned_number[1] in '123467':
        return 'Saudi Arabia Landline'
    
    # International call
    if cleaned_number.startswith('00') or number.startswith('+'):
        # Remove leading '00' or '+'
        if cleaned_number.startswith('00'):
            international_number = cleaned_number[2:]
        else:
            international_number = cleaned_number[1:] if number.startswith('+') else cleaned_number
        
        # Check against country codes
        for code, country in COUNTRY_CODES.items():
            if international_number.startswith(code):
                return country
        
        # If no match found in COUNTRY_CODES
        return 'International - Unknown Country'
    
    # If none of the above conditions are met
    return 'Unknown'


def get_date_range(request):
    now = timezone.now()
    time_period = request.GET.get('time_period', 'today')
    custom_date_range = request.GET.get('custom_date', '')

    if time_period == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    elif time_period == '7d':
        start_date = now - timedelta(days=7)
        end_date = now
    elif time_period == '1m':
        start_date = now - timedelta(days=30)
        end_date = now
    elif time_period == '6m':
        start_date = now - timedelta(days=182)
        end_date = now
    elif time_period == '1y':
        start_date = now - timedelta(days=365)
        end_date = now
    elif time_period == 'custom' and custom_date_range:
        start_date_str, end_date_str = custom_date_range.split(" to ")
        start_date = timezone.make_aware(datetime.strptime(start_date_str, "%d %b, %Y"))
        end_date = timezone.make_aware(datetime.strptime(end_date_str, "%d %b, %Y").replace(hour=23, minute=59, second=59))
    else:
        start_date = now
        end_date = now

    return start_date, end_date, time_period, custom_date_range


