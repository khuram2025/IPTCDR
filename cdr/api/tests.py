"""End-to-end API + webhook tests.

Covers the new public-API surface added in Phase 1: API-key auth, tenant
scoping, OpenAPI schema, and HMAC-signed webhook delivery.
"""
import hashlib
import hmac
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Company, Currency
from cdr3cx.models import CallRecord
from billing.models import FraudIncident, FraudRule

from .models import ApiKey, WebhookDelivery, WebhookSubscription
from .services.webhooks import deliver_now, emit, sign


# Disable throttling for everything except the dedicated throttling tests
THROTTLE_OFF = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'api.auth.ApiKeyAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}


@override_settings(REST_FRAMEWORK=THROTTLE_OFF)
class ApiKeyAuthTests(TestCase):

    def setUp(self):
        self.sar, _ = Currency.objects.get_or_create(
            code='SAR', defaults={'name': 'Saudi Riyal', 'symbol': 'ر.س'},
        )
        self.company = Company.objects.create(name='AcmeCo', currency=self.sar, country_code='SA')
        self.other = Company.objects.create(name='Other', currency=self.sar, country_code='SA')

        self.api_key, self.plaintext = ApiKey.generate(self.company, name='test', tier='paid')
        self.client = APIClient()

    def test_generate_returns_plaintext_only_once(self):
        self.assertEqual(len(self.plaintext), 40)
        self.assertEqual(self.api_key.key_prefix, self.plaintext[:8])
        self.assertNotEqual(self.api_key.key_hash, self.plaintext)
        self.assertEqual(
            self.api_key.key_hash,
            hashlib.sha256(self.plaintext.encode()).hexdigest(),
        )

    def test_lookup_finds_active_key(self):
        found = ApiKey.lookup(self.plaintext)
        self.assertEqual(found.pk, self.api_key.pk)

    def test_lookup_misses_revoked_key(self):
        self.api_key.is_active = False
        self.api_key.save()
        self.assertIsNone(ApiKey.lookup(self.plaintext))

    def test_unauthenticated_request_rejected(self):
        resp = self.client.get('/api/v1/extensions/')
        self.assertEqual(resp.status_code, 401)

    def test_bearer_header_authenticates(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.plaintext}')
        resp = self.client.get('/api/v1/extensions/')
        self.assertEqual(resp.status_code, 200)

    def test_x_api_key_header_authenticates(self):
        self.client.credentials(HTTP_X_API_KEY=self.plaintext)
        resp = self.client.get('/api/v1/extensions/')
        self.assertEqual(resp.status_code, 200)

    def test_invalid_key_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not-a-real-key')
        resp = self.client.get('/api/v1/extensions/')
        self.assertEqual(resp.status_code, 401)

    def test_tenant_isolation_on_call_records(self):
        CallRecord.objects.create(company=self.company, callee='100', caller='200', source_pbx='3cx')
        CallRecord.objects.create(company=self.other,   callee='300', caller='400', source_pbx='3cx')

        self.client.credentials(HTTP_X_API_KEY=self.plaintext)
        resp = self.client.get('/api/v1/call-records/')
        self.assertEqual(resp.status_code, 200)
        callees = [r['callee'] for r in resp.json()['results']]
        self.assertIn('100', callees)
        self.assertNotIn('300', callees)


@override_settings(REST_FRAMEWORK=THROTTLE_OFF)
class HealthAndSchemaTests(TestCase):

    def test_health_unauthenticated(self):
        resp = self.client.get('/api/v1/health/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'ok')

    def test_openapi_schema_renders(self):
        resp = self.client.get('/api/schema/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'IPT Portal API', resp.content)


@override_settings(REST_FRAMEWORK=THROTTLE_OFF)
class WebhookDeliveryTests(TestCase):

    def setUp(self):
        self.sar, _ = Currency.objects.get_or_create(code='SAR', defaults={'name': 'SAR', 'symbol': 'ر.س'})
        self.company = Company.objects.create(name='WhCo', currency=self.sar, country_code='SA')
        self.sub = WebhookSubscription.objects.create(
            company=self.company,
            name='Test sub',
            url='https://example.invalid/hook',
            events=['call.completed', 'fraud.detected'],
            secret=WebhookSubscription.generate_secret(),
        )

    def test_signature_is_deterministic_hmac(self):
        body = b'{"hello":"world"}'
        sig = sign(self.sub.secret, body)
        expected = hmac.new(self.sub.secret.encode(), body, hashlib.sha256).hexdigest()
        self.assertEqual(sig, f'sha256={expected}')

    def _patched_post(self, status_code=200, body='OK'):
        mock = MagicMock(status_code=status_code, text=body)
        return patch('api.services.webhooks.requests.post', return_value=mock)

    def test_successful_delivery_marks_delivered(self):
        with self._patched_post(200) as mocked:
            count = emit(self.company, 'call.completed', {'id': 1, 'caller': '100'})
        self.assertEqual(count, 1)
        delivery = WebhookDelivery.objects.get(subscription=self.sub)
        self.assertEqual(delivery.status, 'delivered')
        self.assertEqual(delivery.attempts, 1)
        self.assertEqual(delivery.last_status_code, 200)
        args, kwargs = mocked.call_args
        self.assertEqual(args[0], 'https://example.invalid/hook')
        self.assertIn('X-IPTPortal-Signature', kwargs['headers'])
        self.assertIn('X-IPTPortal-Event', kwargs['headers'])

    def test_event_not_subscribed_skips(self):
        with self._patched_post(200):
            count = emit(self.company, 'invoice.paid', {'id': 1})
        self.assertEqual(count, 0)
        self.assertFalse(WebhookDelivery.objects.exists())

    def test_failed_delivery_schedules_retry(self):
        with self._patched_post(500, body='boom'):
            emit(self.company, 'call.completed', {'id': 99})
        delivery = WebhookDelivery.objects.get()
        self.assertEqual(delivery.status, 'pending')
        self.assertEqual(delivery.attempts, 1)
        self.assertIsNotNone(delivery.next_retry_at)

    def test_retries_exhausted_marks_failed(self):
        with self._patched_post(500):
            emit(self.company, 'call.completed', {'id': 99})
            delivery = WebhookDelivery.objects.get()
            for _ in range(5):
                if delivery.status in ('failed', 'delivered'):
                    break
                deliver_now(delivery)
                delivery.refresh_from_db()
        self.assertEqual(delivery.status, 'failed')
        self.assertGreaterEqual(delivery.attempts, 4)
        self.sub.refresh_from_db()
        self.assertGreaterEqual(self.sub.consecutive_failures, 1)

    def test_signal_fan_out_on_call_record_create(self):
        with self._patched_post(200) as mocked:
            CallRecord.objects.create(
                company=self.company, caller='100', callee='200', source_pbx='3cx',
            )
        self.assertTrue(mocked.called)
        delivery = WebhookDelivery.objects.get()
        self.assertEqual(delivery.event_type, 'call.completed')

    def test_signal_fan_out_on_fraud_incident(self):
        rule = FraudRule.objects.create(
            company=self.company, name='Test rule', rule_type='intl_spike',
            threshold=1, severity='high', action='alert',
        )
        with self._patched_post(200) as mocked:
            FraudIncident.objects.create(
                company=self.company, rule=rule, severity='high',
                summary='intl spike', detail={},
            )
        self.assertTrue(mocked.called)
        events = list(WebhookDelivery.objects.values_list('event_type', flat=True))
        self.assertIn('fraud.detected', events)


@override_settings(REST_FRAMEWORK={
    **THROTTLE_OFF,
    'DEFAULT_THROTTLE_CLASSES': ['api.throttling.ApiKeyScopedThrottle'],
    'DEFAULT_THROTTLE_RATES': {'api_key.free': '2/min', 'api_key.paid': '10/min', 'api_key.pro': '100/min'},
})
class ThrottlingTests(TestCase):

    def setUp(self):
        self.sar, _ = Currency.objects.get_or_create(code='SAR', defaults={'name': 'SAR', 'symbol': 'ر.س'})
        self.company = Company.objects.create(name='ThrottleCo', currency=self.sar, country_code='SA')
        self.api_key, self.plaintext = ApiKey.generate(self.company, name='free', tier='free')
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY=self.plaintext)

    def test_rate_limit_kicks_in_after_quota(self):
        for _ in range(2):
            self.assertEqual(self.client.get('/api/v1/extensions/').status_code, 200)
        resp = self.client.get('/api/v1/extensions/')
        self.assertEqual(resp.status_code, 429)
