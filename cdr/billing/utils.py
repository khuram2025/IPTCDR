import phonenumbers
from phonenumbers import geocoder, carrier, PhoneNumberType, NumberParseException

def get_phone_number_info(phone_number_str):
    try:
        # Try parsing without a region first
        phone_number = phonenumbers.parse(phone_number_str, None)
        
        if not phonenumbers.is_valid_number(phone_number):
            return {"error": "Invalid phone number"}
        
        number_type = phonenumbers.number_type(phone_number)
        type_str = {
            PhoneNumberType.MOBILE: "Mobile",
            PhoneNumberType.FIXED_LINE: "Fixed line",
            PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed line or mobile",
            PhoneNumberType.TOLL_FREE: "Toll free",
            PhoneNumberType.PREMIUM_RATE: "Premium rate",
            PhoneNumberType.SHARED_COST: "Shared cost",
            PhoneNumberType.VOIP: "VoIP",
            PhoneNumberType.PERSONAL_NUMBER: "Personal number",
            PhoneNumberType.PAGER: "Pager",
            PhoneNumberType.UAN: "UAN",
            PhoneNumberType.VOICEMAIL: "Voicemail",
        }.get(number_type, "Unknown")
        
        country = geocoder.country_name_for_number(phone_number, "en")
        carrier_name = carrier.name_for_number(phone_number, "en")
        
        return {
            "phone_number": phonenumbers.format_number(phone_number, phonenumbers.PhoneNumberFormat.E164),
            "country": country,
            "carrier": carrier_name,
            "type": type_str
        }
    except NumberParseException as e:
        return {"error": str(e)}

# Example usage
phone_info = get_phone_number_info("+14155552671")  # International format
print(phone_info)

phone_info = get_phone_number_info("0590964890")  # Local format, may need region
print(phone_info)
