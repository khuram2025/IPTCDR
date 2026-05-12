from django.contrib import admin

from .models import ApiKey, WebhookDelivery, WebhookSubscription


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ('company', 'name', 'key_prefix', 'tier', 'is_active',
                    'last_used_at', 'created_at')
    list_filter = ('tier', 'is_active', 'company')
    search_fields = ('name', 'key_prefix', 'company__name')
    readonly_fields = ('key_hash', 'key_prefix', 'created_at', 'last_used_at')


@admin.register(WebhookSubscription)
class WebhookSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('company', 'name', 'url', 'is_active',
                    'consecutive_failures', 'last_success_at')
    list_filter = ('is_active', 'company')
    search_fields = ('name', 'url', 'company__name')


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'subscription', 'status', 'attempts',
                    'last_status_code', 'created_at', 'delivered_at')
    list_filter = ('status', 'event_type')
    search_fields = ('event_type', 'subscription__name')
    readonly_fields = ('attempts', 'last_status_code', 'last_response_excerpt',
                       'created_at', 'delivered_at')
