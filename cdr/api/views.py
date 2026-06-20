"""DRF viewsets for the public API.

All querysets are scoped by ``request.user.company`` (works for both API-key
and session auth, since both expose ``.company`` on the user).
"""
import json
import logging

from django.utils.dateparse import parse_date
from rest_framework import mixins, viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from accounts.models import Company, Currency, Extension
from billing.models import FraudIncident, FraudRule, TaxRule
from cdr3cx.models import CallPattern, CallRecord, Quota, UserQuota

from surveys.models import SurveyCampaign, SurveyResponse
from surveys.services.ingest import IngestError, ingest_survey_response, resolve_campaign_from_token
from surveys.services.metrics import survey_dashboard_metrics
from surveys.tasks import post_survey_ingest

from .models import ApiKey, WebhookSubscription
from .serializers import (
    ApiKeyCreateSerializer, ApiKeySerializer,
    CallPatternSerializer, CallRecordSerializer, CompanySerializer,
    CurrencySerializer, ExtensionSerializer, FraudIncidentSerializer,
    FraudRuleSerializer, QuotaSerializer, TaxRuleSerializer,
    UserQuotaSerializer, WebhookSubscriptionSerializer,
    SurveyCampaignSerializer, SurveyResponseSerializer,
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


class SurveyIngestThrottle(AnonRateThrottle):
    rate = '120/min'


_ingest_logger = logging.getLogger('survey_ingest')


def _ingest_client_ip(request):
    """Real visitor IP. Prefers Cloudflare's header, then XFF, then REMOTE_ADDR."""
    cf = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf:
        return cf.strip()
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '-')


def _mask_token(token):
    token = (token or '').strip()
    if not token:
        return '(none)'
    return f'{token[:4]}…{token[-4:]}' if len(token) > 10 else '****'


class SurveyIngestView(APIView):
    """CFD POST endpoint — authenticated via X-Survey-Token per campaign."""
    authentication_classes: list = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [SurveyIngestThrottle]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        # Log EVERY hit to this endpoint (any method) with request + response.
        try:
            try:
                req_body = json.dumps(request.data, ensure_ascii=False, default=str)
            except Exception:
                req_body = '<unparseable body>'
            try:
                resp_body = json.dumps(response.data, ensure_ascii=False, default=str)
            except Exception:
                resp_body = '<no data>'
            _ingest_logger.info(
                'HIT %s ip=%s ua=%r token=%s\n  REQUEST : %s\n  RESPONSE %s: %s',
                request.method,
                _ingest_client_ip(request),
                request.META.get('HTTP_USER_AGENT', '-'),
                _mask_token(request.META.get('HTTP_X_SURVEY_TOKEN')),
                req_body,
                response.status_code,
                resp_body,
            )
        except Exception:  # never let logging break the API
            _ingest_logger.exception('Failed to log ingest hit')
        return response

    def post(self, request):
        token = request.META.get('HTTP_X_SURVEY_TOKEN', '').strip()
        try:
            campaign = resolve_campaign_from_token(token)
            slug = (request.data.get('campaign_slug') or '').strip()
            if slug and slug != campaign.slug:
                return Response({'detail': 'campaign_slug does not match token'}, status=400)
            response, created = ingest_survey_response(campaign, request.data)
            if created:
                post_survey_ingest.delay(response.pk)
            code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
            return Response({
                'id': response.pk,
                'created': created,
                'match_confidence': response.match_confidence,
                'call_record_id': response.call_record_id,
            }, status=code)
        except IngestError as exc:
            return Response({'detail': str(exc)}, status=exc.status_code)


class SurveyCampaignViewSet(_TenantScopedMixin, viewsets.ModelViewSet):
    queryset = SurveyCampaign.objects.prefetch_related('questions')
    serializer_class = SurveyCampaignSerializer
    required_scopes = ['read:surveys']
    search_fields = ['name', 'slug']
    ordering_fields = ['name', 'created_at']

    def initial(self, request, *args, **kwargs):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            self.required_scopes = ['write:surveys']
        else:
            self.required_scopes = ['read:surveys']
        super().initial(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class SurveyResponseViewSet(_TenantScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = SurveyResponse.objects.select_related(
        'campaign', 'agent', 'queue', 'call_record',
    ).prefetch_related('answers').order_by('-completed_at')
    serializer_class = SurveyResponseSerializer
    required_scopes = ['read:surveys']
    search_fields = ['caller']
    ordering_fields = ['completed_at', 'caller']

    def get_queryset(self):
        qs = super().get_queryset()
        since = self.request.query_params.get('since')
        until = self.request.query_params.get('until')
        if since:
            qs = qs.filter(completed_at__gte=since)
        if until:
            qs = qs.filter(completed_at__lte=until)
        campaign = self.request.query_params.get('campaign')
        if campaign:
            qs = qs.filter(campaign_id=campaign)
        agent = self.request.query_params.get('agent')
        if agent:
            qs = qs.filter(agent_id=agent)
        queue = self.request.query_params.get('queue')
        if queue:
            qs = qs.filter(queue_id=queue)
        return qs


class SurveyMetricsView(APIView):
    """Aggregated CSAT/NPS metrics for a date range."""
    required_scopes = ['read:surveys']

    def get(self, request):
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({'detail': 'No company'}, status=400)
        since = parse_date(request.query_params.get('since') or '')
        until = parse_date(request.query_params.get('until') or '')
        if not since or not until:
            from django.utils import timezone
            until = timezone.localdate()
            since = until.replace(day=1)
        data = survey_dashboard_metrics(company, since, until)
        return Response(data)
