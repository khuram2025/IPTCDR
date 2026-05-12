"""DRF viewsets for the public API.

All querysets are scoped by ``request.user.company`` (works for both API-key
and session auth, since both expose ``.company`` on the user).
"""
from rest_framework import mixins, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Company, Currency, Extension
from billing.models import FraudIncident, FraudRule, TaxRule
from cdr3cx.models import CallPattern, CallRecord, Quota, UserQuota

from .models import ApiKey, WebhookSubscription
from .serializers import (
    ApiKeyCreateSerializer, ApiKeySerializer,
    CallPatternSerializer, CallRecordSerializer, CompanySerializer,
    CurrencySerializer, ExtensionSerializer, FraudIncidentSerializer,
    FraudRuleSerializer, QuotaSerializer, TaxRuleSerializer,
    UserQuotaSerializer, WebhookSubscriptionSerializer,
)


class _TenantScopedMixin:
    """Filter queryset by ``request.user.company``."""

    company_field = 'company'

    def get_queryset(self):
        qs = super().get_queryset()
        company = getattr(self.request.user, 'company', None)
        if company is None:
            return qs.none()
        return qs.filter(**{self.company_field: company})


class CurrencyViewSet(viewsets.ReadOnlyModelViewSet):
    """Currencies are global reference data, not tenant-scoped."""
    queryset = Currency.objects.filter(is_active=True)
    serializer_class = CurrencySerializer
    pagination_class = None  # small list, no need to paginate


class CompanyViewSet(viewsets.ReadOnlyModelViewSet):
    """Returns only the caller's own company."""
    serializer_class = CompanySerializer

    def get_queryset(self):
        company = getattr(self.request.user, 'company', None)
        return Company.objects.filter(pk=company.pk) if company else Company.objects.none()


class ExtensionViewSet(_TenantScopedMixin, viewsets.ModelViewSet):
    queryset = Extension.objects.all()
    serializer_class = ExtensionSerializer
    search_fields = ['extension', 'first_name', 'last_name', 'full_name', 'email']
    ordering_fields = ['extension', 'full_name']
    required_scopes = ['read:extensions']


class CallRecordViewSet(_TenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = CallRecord.objects.all().order_by('-call_time')
    serializer_class = CallRecordSerializer
    search_fields = ['caller', 'callee', 'from_dispname', 'to_dispname', 'final_dispname']
    ordering_fields = ['call_time', 'duration', 'total_cost']
    required_scopes = ['read:cdr']

    def get_queryset(self):
        qs = super().get_queryset()
        # Optional date filtering via query params: ?since=ISO8601&until=ISO8601
        since = self.request.query_params.get('since')
        until = self.request.query_params.get('until')
        if since:
            qs = qs.filter(call_time__gte=since)
        if until:
            qs = qs.filter(call_time__lte=until)
        source_pbx = self.request.query_params.get('source_pbx')
        if source_pbx:
            qs = qs.filter(source_pbx=source_pbx)
        return qs


class CallPatternViewSet(_TenantScopedMixin, viewsets.ModelViewSet):
    queryset = CallPattern.objects.all()
    serializer_class = CallPatternSerializer


class QuotaViewSet(viewsets.ReadOnlyModelViewSet):
    """Quotas don't have a direct company FK in the current schema; expose all
    quotas the company's extensions reference."""
    serializer_class = QuotaSerializer

    def get_queryset(self):
        company = getattr(self.request.user, 'company', None)
        if company is None:
            return Quota.objects.none()
        # Quotas linked via UserQuota -> Extension -> Company
        quota_ids = UserQuota.objects.filter(extension__company=company).values_list('quota_id', flat=True)
        return Quota.objects.filter(pk__in=quota_ids)


class UserQuotaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserQuotaSerializer

    def get_queryset(self):
        company = getattr(self.request.user, 'company', None)
        if company is None:
            return UserQuota.objects.none()
        return UserQuota.objects.filter(extension__company=company)


class TaxRuleViewSet(viewsets.ReadOnlyModelViewSet):
    """Returns global tax rules + tenant-specific overrides."""
    serializer_class = TaxRuleSerializer

    def get_queryset(self):
        from django.db.models import Q
        company = getattr(self.request.user, 'company', None)
        qs = TaxRule.objects.filter(is_active=True)
        if company is None:
            return qs.filter(company__isnull=True)
        # Django doesn't match NULL via ``__in=[None, …]`` — combine with Q.
        return qs.filter(Q(company__isnull=True) | Q(company=company))


class FraudRuleViewSet(_TenantScopedMixin, viewsets.ModelViewSet):
    queryset = FraudRule.objects.all()
    serializer_class = FraudRuleSerializer


class FraudIncidentViewSet(_TenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = FraudIncident.objects.all()
    serializer_class = FraudIncidentSerializer
    ordering_fields = ['detected_at', 'severity']
    required_scopes = ['read:fraud']

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        incident = self.get_object()
        incident.status = 'acknowledged'
        incident.save(update_fields=['status'])
        return Response(self.get_serializer(incident).data)

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        from django.utils import timezone
        incident = self.get_object()
        incident.status = 'resolved'
        incident.resolved_at = timezone.now()
        # Only set resolved_by for session-authenticated users
        if request.user.is_authenticated and not hasattr(request.user, 'api_key'):
            incident.resolved_by = request.user
        incident.save(update_fields=['status', 'resolved_at', 'resolved_by'])
        return Response(self.get_serializer(incident).data)


class ApiKeyViewSet(mixins.ListModelMixin, mixins.CreateModelMixin,
                    mixins.RetrieveModelMixin, mixins.DestroyModelMixin,
                    viewsets.GenericViewSet):
    """Manage API keys via the API itself (or the customer portal UI).

    On POST, the response body includes ``plaintext`` — store it; it cannot be
    retrieved again.
    """

    def get_queryset(self):
        company = getattr(self.request.user, 'company', None)
        return ApiKey.objects.filter(company=company) if company else ApiKey.objects.none()

    def get_serializer_class(self):
        return ApiKeyCreateSerializer if self.action == 'create' else ApiKeySerializer

    def perform_destroy(self, instance):
        from django.utils import timezone
        instance.is_active = False
        instance.revoked_at = timezone.now()
        instance.save(update_fields=['is_active', 'revoked_at'])


class WebhookSubscriptionViewSet(_TenantScopedMixin, viewsets.ModelViewSet):
    queryset = WebhookSubscription.objects.all()
    serializer_class = WebhookSubscriptionSerializer

    @action(detail=True, methods=['post'])
    def rotate_secret(self, request, pk=None):
        sub = self.get_object()
        sub.secret = WebhookSubscription.generate_secret()
        sub.save(update_fields=['secret'])
        return Response({'secret': sub.secret})


class HealthView(APIView):
    """Unauthenticated health check for monitoring."""
    authentication_classes: list = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({'status': 'ok', 'service': 'iptportal-api', 'version': '1.0.0'})
