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
    was_saudi_intl = False
    if cleaned_number.startswith('00966'):
        cleaned_number = cleaned_number[5:]  # Remove '00966'
        was_saudi_intl = True
    elif cleaned_number.startswith('966') and len(cleaned_number) > 9:
        cleaned_number = cleaned_number[3:]  # Remove '966' when prefixed by '+'
        was_saudi_intl = True

    if len(cleaned_number) == 9 and cleaned_number.startswith('5'):
        return 'Saudi Arabia Mobile'

    # Saudi Arabia landline (9 digits starting with 01, 02, 03, 04, 06, 07)
    if len(cleaned_number) == 9 and cleaned_number[0] == '0' and cleaned_number[1] in '123467':
        return 'Saudi Arabia Landline'

    # Any number that carried the Saudi country code (+966 / 00966) is a Saudi
    # number — e.g. 920/9200 unified-access or business numbers, or landlines in
    # international format. It must NOT fall through to the international block
    # (stripping '966' then re-stripping a digit used to mis-match +966 9200…
    # numbers to Egypt's +20 / Pakistan's +92).
    if was_saudi_intl:
        return 'Saudi Arabia'

    # International call
    if cleaned_number.startswith('00') or number.startswith('+'):
        # Determine the dialled number including its country code. re.sub already
        # stripped the leading '+', so a '+'-prefixed number is the full number;
        # only a '00' trunk prefix needs removing.
        if cleaned_number.startswith('00'):
            international_number = cleaned_number[2:]
        else:
            international_number = cleaned_number

        # Check against country codes (longest code first so e.g. +1242 beats +1)
        for code, country in sorted(COUNTRY_CODES.items(), key=lambda kv: -len(kv[0])):
            if international_number.startswith(code):
                return country

        # If no match found in COUNTRY_CODES
        return 'International - Unknown Country'
    
    # If none of the above conditions are met
    return 'Unknown'


def get_date_range(request):
    # Local (Asia/Riyadh) time so "today" starts at local midnight, not UTC midnight.
    now = timezone.localtime(timezone.now())
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
    elif time_period == 'month':
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
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


