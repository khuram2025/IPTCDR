from django import template
from datetime import timedelta
register = template.Library()

@register.filter
def format_from_no(value):
    if value.startswith("Ext."):
        return value[4:]
    return "0" + value

@register.filter
def sub(value, arg):
    return value - arg

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

@register.filter
def format_duration(value):
    if value is None:
        return "0:00:00"
    total_seconds = int(value)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"

@register.simple_tag
def url_replace(request, field, value):
    dict_ = request.GET.copy()
    dict_[field] = value
    return dict_.urlencode()


