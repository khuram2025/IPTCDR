from django import template

register = template.Library()

@register.filter
def company_initials(company_name):
    """
    Extract initials from company name for avatar display.
    Examples:
    - "Smasco" -> "SM"
    - "SAMNAN" -> "SA"
    - "Company Name" -> "CN"
    """
    if not company_name:
        return "NA"
    
    # Split by spaces and take first letter of each word
    words = company_name.split()
    if len(words) >= 2:
        # If multiple words, take first letter of first two words
        return (words[0][0] + words[1][0]).upper()
    elif len(words) == 1:
        # If single word, take first two letters
        word = words[0]
        if len(word) >= 2:
            return word[:2].upper()
        else:
            return word[0].upper() + "A"
    else:
        return "NA"