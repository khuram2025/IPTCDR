import re
from .project_numbers import COUNTRY_CODES

def get_country_from_number(number):
    # Remove any non-digit characters from the number
    cleaned_number = re.sub(r'\D', '', number)
    
    # Internal company call (4 digits)
    if len(cleaned_number) == 4:
        return 'Internal Company Call'
    
    # Saudi Arabia mobile number (10 digits starting with 05)
    if len(cleaned_number) == 10 and cleaned_number.startswith('05'):
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
                return f"International - {country}"
        
        # If no match found in COUNTRY_CODES
        return 'International - Unknown Country'
    
    # If none of the above conditions are met
    return 'Unknown'



