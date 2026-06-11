from django.contrib import admin

from .models import (
    TaxRule, FraudRule, FraudIncident, Invoice, InvoiceLineItem, Payment,
)


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 0


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('number', 'company', 'period_start', 'period_end', 'currency',
                    'subtotal', 'tax_amount', 'total', 'status')
    list_filter = ('company', 'status', 'currency')
    search_fields = ('number',)
    inlines = [InvoiceLineItemInline, PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount', 'currency', 'method', 'paid_at')
    list_filter = ('method', 'currency')


for _m in (TaxRule, FraudRule, FraudIncident):
    try:
        admin.site.register(_m)
    except admin.sites.AlreadyRegistered:
        pass
