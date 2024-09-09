from django.contrib import admin
from django.db.models import Count, Sum
from django.shortcuts import render

from accounts.models import Company
from .models import CallPattern, CallRecord

@admin.register(CallPattern)
class CallPatternAdmin(admin.ModelAdmin):
    list_display = ('company', 'pattern', 'call_type', 'description')
    search_fields = ('company__name', 'pattern', 'call_type')
    list_filter = ('company', 'call_type')

@admin.register(CallRecord)
class CallRecordAdmin(admin.ModelAdmin):
    list_display = (
        'caller', 'callee', 'call_time', 'external_number', 'duration', 
        'time_answered', 'time_end', 'reason_terminated', 'reason_changed', 
        'missed_queue_calls', 'from_no', 'to_no', 'to_dn', 'final_number', 
        'final_dn', 'from_type', 'to_type', 'final_type', 'from_dispname', 
        'to_dispname', 'final_dispname'
    )
    list_filter = ('call_time','from_type','from_no', 'callee')
    search_fields = ('caller', 'callee', 'external_number', 'from_no', 'to_no', 'final_number')
    date_hierarchy = 'call_time'


from .models import Quota, UserQuota


@admin.register(UserQuota)
class UserQuotaAdmin(admin.ModelAdmin):
    list_display = ('extension', 'quota', 'remaining_balance', 'last_reset')
    list_filter = ('quota', 'last_reset')
    search_fields = ('extension__extension', 'extension__full_name', 'remaining_balance')
    ordering = ('extension__extension', 'remaining_balance')
    actions = ['reset_quotas']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('extension', 'quota')

    def reset_quotas(self, request, queryset):
        for user_quota in queryset:
            user_quota.reset_quota()
            user_quota.save()
        self.message_user(request, f"{queryset.count()} quotas were reset successfully.")
    reset_quotas.short_description = "Reset selected quotas"

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        
        try:
            # Search for exact matches in remaining_balance
            balance = float(search_term)
            queryset |= self.model.objects.filter(remaining_balance=balance)
        except ValueError:
            # If search_term is not a valid float, ignore this part
            pass

        return queryset, use_distinct

@admin.register(Quota)
class QuotaAdmin(admin.ModelAdmin):
    list_display = ('name', 'amount', 'company')