from django.contrib import admin

from .models import AlertRule, AlertEvent


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'source', 'min_severity', 'channels',
                    'escalate_after_minutes', 'is_active')
    list_filter = ('source', 'is_active', 'company')
    search_fields = ('name', 'recipients')


@admin.register(AlertEvent)
class AlertEventAdmin(admin.ModelAdmin):
    list_display = ('source', 'severity', 'company', 'summary', 'channels_sent',
                    'delivered', 'escalated', 'created_at')
    list_filter = ('source', 'severity', 'delivered', 'escalated', 'company')
    readonly_fields = ('created_at',)
