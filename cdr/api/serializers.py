"""DRF serializers for the public API."""
from rest_framework import serializers

from accounts.models import Company, Currency, Extension
from billing.models import FraudIncident, FraudRule, TaxRule
from cdr3cx.models import CallPattern, CallRecord, Quota, UserQuota

from .models import ApiKey, WebhookSubscription


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name', 'symbol', 'decimals', 'is_active']


class CompanySerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)

    class Meta:
        model = Company
        fields = ['id', 'name', 'address', 'phone', 'country_code',
                  'currency', 'vat_number', 'listening_port']


class ExtensionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Extension
        fields = ['id', 'extension', 'first_name', 'last_name', 'full_name',
                  'email', 'company', 'disable_external_call']


class CallRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallRecord
        fields = [
            'id', 'source_pbx', 'external_id', 'correlation_id',
            'caller', 'callee', 'call_time', 'time_answered', 'time_end',
            'duration', 'country', 'reason_terminated',
            'from_dispname', 'to_dispname', 'final_dispname',
            'from_type', 'to_type', 'final_type',
            'call_category', 'call_rate', 'total_cost',
            'mos', 'jitter_ms', 'packet_loss_pct', 'latency_ms', 'codec',
        ]


class CallPatternSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallPattern
        fields = ['id', 'company', 'name', 'pattern', 'call_type',
                  'rate_per_min', 'description']


class QuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quota
        fields = '__all__'


class UserQuotaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserQuota
        fields = '__all__'


class TaxRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRule
        fields = ['id', 'name', 'country_code', 'rate_percent', 'applies_to',
                  'effective_from', 'effective_to', 'company', 'is_active']


class FraudRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraudRule
        fields = ['id', 'company', 'name', 'rule_type', 'threshold',
                  'time_window_minutes', 'countries', 'severity', 'action',
                  'notify_emails', 'notify_sms', 'is_active', 'shadow_mode',
                  'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class FraudIncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraudIncident
        fields = ['id', 'company', 'rule', 'severity', 'summary', 'detail',
                  'triggering_call', 'status', 'detected_at', 'resolved_at',
                  'resolved_by', 'notification_dispatched', 'action_executed']
        read_only_fields = ['detected_at']


class ApiKeySerializer(serializers.ModelSerializer):
    """Read serializer — never exposes the plaintext key (set on creation only)."""

    class Meta:
        model = ApiKey
        fields = ['id', 'name', 'key_prefix', 'tier', 'scopes',
                  'created_at', 'last_used_at', 'expires_at', 'is_active']
        read_only_fields = ['key_prefix', 'created_at', 'last_used_at']


class ApiKeyCreateSerializer(serializers.ModelSerializer):
    plaintext = serializers.CharField(read_only=True,
                                      help_text="The full API key — shown once, never again")

    class Meta:
        model = ApiKey
        fields = ['id', 'name', 'tier', 'scopes', 'expires_at', 'plaintext']

    def create(self, validated_data):
        request = self.context['request']
        company = request.user.company
        obj, plaintext = ApiKey.generate(
            company=company,
            name=validated_data['name'],
            tier=validated_data.get('tier', 'paid'),
            scopes=validated_data.get('scopes', []),
            expires_at=validated_data.get('expires_at'),
            created_by=request.user if request.user.is_authenticated and not hasattr(request.user, 'api_key') else None,
        )
        obj.plaintext = plaintext  # one-time return value
        return obj


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookSubscription
        fields = ['id', 'name', 'url', 'events', 'secret', 'is_active',
                  'created_at', 'last_success_at', 'last_failure_at',
                  'consecutive_failures']
        read_only_fields = ['secret', 'created_at', 'last_success_at',
                            'last_failure_at', 'consecutive_failures']

    def create(self, validated_data):
        validated_data['company'] = self.context['request'].user.company
        validated_data['secret'] = WebhookSubscription.generate_secret()
        return super().create(validated_data)
