"""Currency-aware money formatting for templates.

Usage:

    {% load money_tags %}
    {{ invoice.total|money:company.currency }}     -> "ر.س 1,234.50"
    {{ invoice.total|money:"USD" }}                -> "$ 1,234.50"
    {{ invoice.total|money }}                      -> uses request.user.company.currency
                                                       falls back to SAR
"""
from decimal import Decimal, InvalidOperation

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


def _resolve_currency(currency_or_code):
    """Accept a Currency instance, ISO code string, or None."""
    if currency_or_code is None:
        return None
    # Lazy import to avoid circular at module load time
    from accounts.models import Currency

    if isinstance(currency_or_code, Currency):
        return currency_or_code
    try:
        return Currency.objects.get(code=str(currency_or_code).upper())
    except Currency.DoesNotExist:
        return None


@register.filter(name='money')
def money(value, currency=None):
    """Render ``value`` formatted in ``currency``.

    Falls back to SAR if currency is unknown.
    """
    if value is None or value == '':
        return ''
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return value

    cur = _resolve_currency(currency)
    if cur is None:
        # Default to SAR with safe defaults if Currency table is empty
        symbol, decimals = 'ر.س', 2
    else:
        symbol, decimals = cur.symbol, cur.decimals

    # Round to currency-appropriate precision
    quant = Decimal(10) ** -decimals
    amount = amount.quantize(quant)

    # Thousand-separator formatting
    int_part, _, dec_part = f'{amount:,.{decimals}f}'.partition('.')
    formatted = int_part + (f'.{dec_part}' if dec_part else '')

    # Symbol + non-breaking space + amount (RTL-safe)
    return mark_safe(f'{symbol} {formatted}')


@register.simple_tag(takes_context=True)
def tenant_currency(context):
    """Return the current tenant's Currency object (or None)."""
    request = context.get('request')
    if not request or not getattr(request, 'user', None) or not request.user.is_authenticated:
        return None
    company = getattr(request.user, 'company', None)
    return getattr(company, 'currency', None) if company else None
