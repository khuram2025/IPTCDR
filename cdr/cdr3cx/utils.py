import logging


logger = logging.getLogger(__name__)

import re
from .project_numbers import COUNTRY_CODES

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





