from django.contrib import admin
from django import forms
from django.shortcuts import render
from django.http import HttpResponseRedirect
from .models import CallRate, UserQuota
from cdr3cx.models import CallRecord
from accounts.models import Extension

# CallRate Admin Form and Admin
class CallRateAdminForm(forms.ModelForm):
    class Meta:
        model = CallRate
        fields = '__all__'

class CallRateAdmin(admin.ModelAdmin):
    list_display = ('call_type', 'rate_per_min', 'matching_criteria')
    search_fields = ('call_type', 'matching_criteria')
    actions = ['match_call_records']

    def match_call_records(self, request, queryset):
        if 'apply' in request.POST:
            matching_criteria = request.POST['matching_criteria']

            for rate in queryset:
                if rate.matching_criteria:
                    rate.matching_criteria += f",{matching_criteria}"
                else:
                    rate.matching_criteria = matching_criteria
                rate.save()

            self.message_user(request, f"Successfully updated matching criteria for {queryset.count()} call rates.")
            return HttpResponseRedirect(request.get_full_path())
        
        unmatched_criteria = self.get_unmatched_criteria()
        
        # Print debug information
        print("Unmatched criteria:", unmatched_criteria)

        context = {
            'unmatched_criteria': unmatched_criteria,
            'queryset': queryset,
        }
        return render(request, 'admin/match_call_records.html', context)

    def get_unmatched_criteria(self):
        all_callees = CallRecord.objects.values_list('callee', flat=True).distinct()
        existing_criteria = set()
        for rate in CallRate.objects.all():
            existing_criteria.update(rate.matching_criteria.split(','))

        unmatched_criteria = set()
        for callee in all_callees:
            prefix = f"{callee[:2]}xxxxxxxx"
            if prefix not in existing_criteria:
                unmatched_criteria.add(prefix)

        return sorted(unmatched_criteria)

    match_call_records.short_description = "Match selected call rates to criteria"

admin.site.register(CallRate, CallRateAdmin)

# UserQuota Admin Form and Admin
class UserQuotaAdminForm(forms.ModelForm):
    class Meta:
        model = UserQuota
        fields = '__all__'

class UserQuotaAdmin(admin.ModelAdmin):
    list_display = ('extension', 'quota_limit', 'balance', 'balance_frequency', 'calculate_bill','start_date', 'is_recurring', 'is_excluded')
    search_fields = ('extension__extension', 'start_date', 'balance_frequency')
    actions = ['bulk_update']

    def bulk_update(self, request, queryset):
        if 'apply' in request.POST:
            quota_limit = request.POST['quota_limit']
            balance_frequency = request.POST['balance_frequency']
            is_recurring = request.POST['is_recurring']

            for quota in queryset:
                if quota_limit:
                    quota.quota_limit = quota_limit
                if balance_frequency:
                    quota.balance_frequency = balance_frequency
                if is_recurring is not None:
                    quota.is_recurring = is_recurring
                quota.save()

            self.message_user(request, f"Successfully updated {queryset.count()} quotas.")
            return HttpResponseRedirect(request.get_full_path())

        context = {
            'queryset': queryset,
        }
        return render(request, 'admin/bulk_update_quotas.html', context)

    bulk_update.short_description = "Bulk update selected quotas"

admin.site.register(UserQuota, UserQuotaAdmin)

