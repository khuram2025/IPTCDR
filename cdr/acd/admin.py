from django.contrib import admin
from .models import (
    Team, Queue, Agent, QueueMembership, AgentStateEvent,
    Disposition, ThresholdPolicy, CallLeg, Recording,
    ScheduledReport, ReportRun,
)


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'report_type', 'window', 'fmt',
                    'recurrence', 'is_active', 'next_run_at', 'last_run_at')
    list_filter = ('company', 'report_type', 'recurrence', 'is_active')
    search_fields = ('name', 'recipients')


@admin.register(ReportRun)
class ReportRunAdmin(admin.ModelAdmin):
    list_display = ('report_type', 'company', 'fmt', 'window', 'status',
                    'row_count', 'emailed', 'created_at')
    list_filter = ('company', 'report_type', 'status', 'fmt')
    readonly_fields = ('created_at',)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'supervisor', 'is_active')
    list_filter = ('company', 'is_active')


@admin.register(Queue)
class QueueAdmin(admin.ModelAdmin):
    list_display = ('name', 'external_id', 'company', 'sla_target_seconds', 'is_active')
    list_filter = ('company', 'source_pbx', 'is_active')
    search_fields = ('name', 'external_id')


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'external_id', 'company', 'extension', 'is_active')
    list_filter = ('company', 'is_active')
    search_fields = ('display_name', 'external_id')


@admin.register(QueueMembership)
class QueueMembershipAdmin(admin.ModelAdmin):
    list_display = ('agent', 'queue', 'priority', 'is_active')


@admin.register(AgentStateEvent)
class AgentStateEventAdmin(admin.ModelAdmin):
    list_display = ('agent', 'state', 'reason_code', 'started_at', 'ended_at')
    list_filter = ('state',)


@admin.register(Disposition)
class DispositionAdmin(admin.ModelAdmin):
    list_display = ('code', 'label', 'company', 'is_resolution', 'is_active')


@admin.register(ThresholdPolicy)
class ThresholdPolicyAdmin(admin.ModelAdmin):
    list_display = ('company', 'queue', 'sla_target_seconds', 'sla_target_pct', 'is_active')


@admin.register(CallLeg)
class CallLegAdmin(admin.ModelAdmin):
    list_display = ('call', 'leg_type', 'queue', 'agent', 'wait_sec', 'talk_sec')


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ('call', 'source_pbx', 'duration_sec', 'created_at')
