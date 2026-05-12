from django.contrib import admin

from .models import (
    AuditLogEntry, CompanyIpWhitelist, CompanySecurityPolicy, PasswordHistory,
)


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'company', 'user_email', 'method', 'path',
                    'status_code', 'ip', 'object_repr')
    list_filter = ('method', 'status_code', 'company')
    search_fields = ('user_email', 'path', 'ip', 'object_repr')
    readonly_fields = [f.name for f in AuditLogEntry._meta.fields]
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False  # audit log is append-only

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # only superuser may purge


@admin.register(CompanyIpWhitelist)
class CompanyIpWhitelistAdmin(admin.ModelAdmin):
    list_display = ('company', 'cidr', 'label', 'is_active', 'created_at')
    list_filter = ('is_active', 'company')
    search_fields = ('cidr', 'label', 'company__name')


@admin.register(CompanySecurityPolicy)
class CompanySecurityPolicyAdmin(admin.ModelAdmin):
    list_display = ('company', 'session_timeout_minutes', 'enforce_ip_whitelist',
                    'require_strong_password', 'password_history_size',
                    'password_max_age_days', 'updated_at')
    list_filter = ('enforce_ip_whitelist', 'require_strong_password')


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    search_fields = ('user__email',)
    readonly_fields = [f.name for f in PasswordHistory._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
