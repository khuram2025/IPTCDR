from django import template

register = template.Library()

@register.filter
def format_from_no(value):
    if value.startswith("Ext."):
        return value[4:]
    return "0" + value

@register.filter
def format_duration(value):
    if value is None:
        return "N/A"

    try:
        seconds = int(value)
    except (ValueError, TypeError):
        return "Invalid duration"

    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    if hours > 0:
        return f"{hours} hour{'s' if hours > 1 else ''} {minutes} minute{'s' if minutes > 1 else ''} {seconds} sec{'s' if seconds > 1 else ''}"
    elif minutes > 0:
        return f"{minutes} minute{'s' if minutes > 1 else ''} {seconds} sec{'s' if seconds > 1 else ''}"
    else:
        return f"{seconds} sec{'s' if seconds > 1 else ''}"
