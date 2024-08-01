from django import template

register = template.Library()

@register.filter
def format_from_no(value):
    if value.startswith("Ext."):
        return value[4:]
    return "0" + value
