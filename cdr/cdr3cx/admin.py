from django.contrib import admin


from .models import CallPattern, CallRecord, RoutingRule

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

@admin.register(RoutingRule)
class RoutingRuleAdmin(admin.ModelAdmin):
    list_display = ('external_number', 'original_caller', 'route_to')
    search_fields = ('external_number', 'original_caller', 'route_to')


