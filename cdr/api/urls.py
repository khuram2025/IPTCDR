"""Public REST API URL routing.

All routes live under ``/api/v1/``. OpenAPI schema at ``/api/schema/`` and
Swagger UI at ``/api/docs/``.
"""
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'currencies',           views.CurrencyViewSet,           basename='currency')
router.register(r'companies',            views.CompanyViewSet,            basename='company')
router.register(r'extensions',           views.ExtensionViewSet,          basename='extension')
router.register(r'call-records',         views.CallRecordViewSet,         basename='callrecord')
router.register(r'call-patterns',        views.CallPatternViewSet,        basename='callpattern')
router.register(r'quotas',               views.QuotaViewSet,              basename='quota')
router.register(r'user-quotas',          views.UserQuotaViewSet,          basename='userquota')
router.register(r'tax-rules',            views.TaxRuleViewSet,            basename='taxrule')
router.register(r'fraud-rules',          views.FraudRuleViewSet,          basename='fraudrule')
router.register(r'fraud-incidents',      views.FraudIncidentViewSet,      basename='fraudincident')
router.register(r'api-keys',             views.ApiKeyViewSet,             basename='apikey')
router.register(r'webhook-subscriptions', views.WebhookSubscriptionViewSet, basename='webhooksubscription')
router.register(r'survey-campaigns', views.SurveyCampaignViewSet, basename='surveycampaign')
router.register(r'survey-responses', views.SurveyResponseViewSet, basename='surveyresponse')

urlpatterns = [
    # Must precede the router — otherwise ``ingest`` is captured as a survey-response pk.
    path('v1/survey-responses/ingest/', views.SurveyIngestView.as_view(), name='survey-ingest'),
    path('v1/survey-metrics/', views.SurveyMetricsView.as_view(), name='survey-metrics'),
    path('v1/', include(router.urls)),
    path('v1/health/', views.HealthView.as_view(), name='api-health'),

    # OpenAPI schema + interactive docs
    path('schema/', SpectacularAPIView.as_view(), name='api-schema'),
    path('docs/',   SpectacularSwaggerView.as_view(url_name='api-schema'), name='api-docs'),
    path('redoc/',  SpectacularRedocView.as_view(url_name='api-schema'),   name='api-redoc'),
]
