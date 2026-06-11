"""Invoice generation (P4.1) with multi-currency + tax wiring (P4.2).

generate_invoice sums a tenant's usage (CallRecord.total_cost) for a period, in the
tenant's billing currency, applies the applicable TaxRule, and writes an Invoice +
per-category line items. By construction the invoice subtotal equals the summed
per-call total_cost (the reconciliation the roadmap exit-criteria requires).
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum, Q
from django.utils import timezone

from billing.models import Invoice, InvoiceLineItem, TaxRule

logger = logging.getLogger(__name__)


def _company_currency(company):
    cur = getattr(company, 'currency', None)
    return getattr(cur, 'code', None) or 'SAR'


def resolve_tax_rule(company, on_date):
    """Active USAGE/BOTH TaxRule for the tenant: company override first, then the
    country default, honouring effective dating. None if no rule applies."""
    base = TaxRule.objects.filter(
        is_active=True, applies_to__in=['USAGE', 'BOTH'],
        effective_from__lte=on_date,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))

    override = base.filter(company=company).order_by('-effective_from').first()
    if override:
        return override
    cc = (getattr(company, 'country_code', '') or '').upper()
    if cc:
        return base.filter(company__isnull=True, country_code=cc).order_by('-effective_from').first()
    return None


def usage_subtotal(company, start, end):
    """(subtotal Decimal, per-category rows) of CallRecord.total_cost in [start,end]."""
    from cdr3cx.models import CallRecord
    qs = CallRecord.objects.filter(company=company, call_time__date__range=[start, end])
    agg = qs.aggregate(s=Sum('total_cost'))
    subtotal = (agg['s'] or Decimal('0'))
    rows = (qs.values('call_category')
            .annotate(calls=Count('id'), cost=Sum('total_cost'))
            .filter(cost__gt=0).order_by('-cost'))
    return Decimal(subtotal), list(rows)


def generate_invoice(company, start, end, *, issue=False, due_days=14):
    """Create/refresh the Invoice for [start, end]. Idempotent on the period.
    Returns the Invoice. A 'paid' invoice is left untouched."""
    existing = Invoice.objects.filter(
        company=company, period_start=start, period_end=end).first()
    if existing and existing.status == Invoice.STATUS_PAID:
        return existing

    subtotal, cat_rows = usage_subtotal(company, start, end)
    subtotal = subtotal.quantize(Decimal('0.01'))
    currency = _company_currency(company)
    rule = resolve_tax_rule(company, end)
    tax_rate = rule.rate_percent if rule else Decimal('0')
    tax_amount = rule.calculate(subtotal) if rule else Decimal('0.00')
    total = (subtotal + tax_amount).quantize(Decimal('0.01'))

    number = f"INV-{company.id}-{start:%Y%m%d}-{end:%Y%m%d}"
    defaults = {
        'number': number, 'currency': currency, 'subtotal': subtotal,
        'tax_rate_percent': tax_rate, 'tax_amount': tax_amount, 'total': total,
        'tax_rule': rule,
    }
    if issue:
        defaults['status'] = Invoice.STATUS_ISSUED
        defaults['issued_at'] = timezone.now()
        defaults['due_date'] = timezone.localdate() + timedelta(days=due_days)

    invoice, _ = Invoice.objects.update_or_create(
        company=company, period_start=start, period_end=end, defaults=defaults)

    # Rebuild line items.
    invoice.line_items.all().delete()
    for r in cat_rows:
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description=f"Usage — {r['call_category'] or 'uncategorised'}",
            category=r['call_category'] or '', quantity=r['calls'],
            amount=Decimal(r['cost']).quantize(Decimal('0.01')))
    if not cat_rows:
        InvoiceLineItem.objects.create(
            invoice=invoice, description='Usage (no billable calls)', amount=Decimal('0.00'))

    logger.info('generate_invoice %s: subtotal=%s tax=%s total=%s %s',
                number, subtotal, tax_amount, total, currency)
    return invoice


def reconcile(invoice):
    """True when the invoice subtotal still equals summed per-call total_cost."""
    subtotal, _ = usage_subtotal(invoice.company, invoice.period_start, invoice.period_end)
    return subtotal.quantize(Decimal('0.01')) == invoice.subtotal
