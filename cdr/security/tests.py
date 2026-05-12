"""Security app tests — audit log, IP whitelist, password policy, scope enforcement."""
from unittest.mock import patch

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.test.utils import override_settings

from accounts.models import Company, Currency, CustomUser
from api.models import ApiKey

from .models import (
    AuditLogEntry, CompanyIpWhitelist, CompanySecurityPolicy, PasswordHistory,
)
from .validators import PasswordHistoryValidator, StrongPasswordValidator


def _mute_webhooks():
    return patch('api.services.webhooks.requests.post', return_value=type(
        'R', (), {'status_code': 200, 'text': 'OK'})())


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class AuditLogMiddlewareTests(TestCase):

    def setUp(self):
        self.sar, _ = Currency.objects.get_or_create(
            code='SAR', defaults={'name': 'SAR', 'symbol': 'ر.س'},
        )
        self.company = Company.objects.create(name='AuditCo', currency=self.sar, country_code='SA')
        self.user = CustomUser.objects.create_user(
            email='auditor@example.com', password='Audit-Pass-12345!', company=self.company.name,
        )
        self._wh = _mute_webhooks(); self._wh.start()

    def tearDown(self):
        self._wh.stop()

    def test_get_request_not_logged(self):
        self.client.force_login(self.user)
        AuditLogEntry.objects.all().delete()
        self.client.get('/realtime/wallboard/heatmap.json')
        # GETs are not in the audited methods set
        self.assertFalse(AuditLogEntry.objects.exists())

    def test_post_request_is_logged(self):
        self.client.force_login(self.user)
        AuditLogEntry.objects.all().delete()
        # Hit any POST endpoint — even a 404 will be audited
        self.client.post('/billing/some-non-existent/', {'foo': 'bar'})
        entries = list(AuditLogEntry.objects.all())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].method, 'POST')
        self.assertEqual(entries[0].user_email, 'auditor@example.com')

    def test_login_recorded_via_signal(self):
        AuditLogEntry.objects.filter(object_repr='LOGIN_SUCCESS').delete()
        # Use the test client to login (calls user_logged_in signal)
        self.assertTrue(self.client.login(email='auditor@example.com', password='Audit-Pass-12345!'))
        self.assertTrue(
            AuditLogEntry.objects.filter(object_repr='LOGIN_SUCCESS', user=self.user).exists(),
        )

    def test_audit_log_view_renders_entries(self):
        AuditLogEntry.objects.create(
            company=self.company, user=self.user, user_email=self.user.email,
            method='POST', path='/some/test/', status_code=200,
        )
        self.client.force_login(self.user)
        r = self.client.get('/security/audit-log/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'/some/test/', r.content)


# ---------------------------------------------------------------------------
# IP whitelist
# ---------------------------------------------------------------------------


class IpWhitelistTests(TestCase):

    def setUp(self):
        self.sar, _ = Currency.objects.get_or_create(code='SAR', defaults={'name': 'SAR', 'symbol': 'ر.س'})
        self.company = Company.objects.create(name='IpCo', currency=self.sar, country_code='SA')
        self.user = CustomUser.objects.create_user(
            email='ip@example.com', password='Strong-Pass-1234!', company=self.company.name,
        )
        # Enforce
        policy = CompanySecurityPolicy.for_company(self.company)
        policy.enforce_ip_whitelist = True
        policy.save()
        # Allow only one specific IP
        CompanyIpWhitelist.objects.create(company=self.company, cidr='198.51.100.0/24', label='office')
        self._wh = _mute_webhooks(); self._wh.start()

    def tearDown(self):
        self._wh.stop()

    def test_listed_ip_allowed(self):
        self.client.force_login(self.user)
        r = self.client.get('/realtime/wallboard/', REMOTE_ADDR='198.51.100.42')
        self.assertEqual(r.status_code, 200)

    def test_unlisted_ip_blocked(self):
        self.client.force_login(self.user)
        r = self.client.get('/realtime/wallboard/', REMOTE_ADDR='10.0.0.1')
        self.assertEqual(r.status_code, 403)
        # Block creates an audit row
        self.assertTrue(
            AuditLogEntry.objects.filter(company=self.company, object_repr='IP_WHITELIST_BLOCK').exists(),
        )

    def test_disabled_policy_does_not_block(self):
        policy = CompanySecurityPolicy.for_company(self.company)
        policy.enforce_ip_whitelist = False
        policy.save()
        self.client.force_login(self.user)
        r = self.client.get('/realtime/wallboard/', REMOTE_ADDR='10.0.0.1')
        self.assertEqual(r.status_code, 200)

    def test_x_forwarded_for_used(self):
        self.client.force_login(self.user)
        r = self.client.get('/realtime/wallboard/',
                            REMOTE_ADDR='10.0.0.1',
                            HTTP_X_FORWARDED_FOR='198.51.100.42, 10.0.0.1')
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------------------
# Password validators
# ---------------------------------------------------------------------------


class StrongPasswordValidatorTests(TestCase):

    def test_short_password_rejected(self):
        with self.assertRaises(ValidationError):
            StrongPasswordValidator().validate('Aa1!short')

    def test_missing_symbol_rejected(self):
        with self.assertRaises(ValidationError):
            StrongPasswordValidator().validate('NoSymbolHere1234')

    def test_missing_uppercase_rejected(self):
        with self.assertRaises(ValidationError):
            StrongPasswordValidator().validate('all-lower-12345!')

    def test_strong_password_accepted(self):
        StrongPasswordValidator().validate('Strong-Pass-Phrase-9!')


class PasswordHistoryValidatorTests(TestCase):

    def setUp(self):
        self.sar, _ = Currency.objects.get_or_create(code='SAR', defaults={'name': 'SAR', 'symbol': 'ر.س'})
        self.company = Company.objects.create(name='PwHistory', currency=self.sar, country_code='SA')
        self.user = CustomUser.objects.create_user(
            email='pw@example.com', password='Initial-Pass-12345!', company=self.company.name,
        )

    def test_new_password_accepted(self):
        PasswordHistoryValidator(history_size=3).validate('Brand-New-Pass-9!', user=self.user)

    def test_reused_password_rejected(self):
        # Set + change passwords — pre_save signal records each old hash
        self.user.set_password('Initial-Pass-12345!'); self.user.save()
        self.user.set_password('Second-Pass-12345!'); self.user.save()
        # Now try to set back to the first
        with self.assertRaises(ValidationError):
            PasswordHistoryValidator(history_size=5).validate('Initial-Pass-12345!', user=self.user)


# ---------------------------------------------------------------------------
# API key scope enforcement
# ---------------------------------------------------------------------------


@override_settings(REST_FRAMEWORK={
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'api.auth.ApiKeyAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
        'api.auth.HasApiKeyScope',
    ],
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
})
class ApiKeyScopeTests(TestCase):

    def setUp(self):
        self.sar, _ = Currency.objects.get_or_create(code='SAR', defaults={'name': 'SAR', 'symbol': 'ر.س'})
        self.company = Company.objects.create(name='ScopeCo', currency=self.sar, country_code='SA')
        self.client_drf = Client()

    def _key(self, scopes):
        _, plain = ApiKey.generate(self.company, name=f'k-{scopes}', tier='paid', scopes=scopes)
        return plain

    def test_empty_scopes_grants_all(self):
        plain = self._key([])
        r = self.client_drf.get('/api/v1/call-records/', HTTP_X_API_KEY=plain)
        self.assertEqual(r.status_code, 200)

    def test_correct_scope_allowed(self):
        plain = self._key(['read:cdr'])
        r = self.client_drf.get('/api/v1/call-records/', HTTP_X_API_KEY=plain)
        self.assertEqual(r.status_code, 200)

    def test_missing_scope_forbidden(self):
        plain = self._key(['read:fraud'])  # not enough for /call-records/ which needs read:cdr
        r = self.client_drf.get('/api/v1/call-records/', HTTP_X_API_KEY=plain)
        self.assertEqual(r.status_code, 403)
        self.assertIn(b'read:cdr', r.content)


# ---------------------------------------------------------------------------
# Per-tenant session timeout
# ---------------------------------------------------------------------------


class SessionTimeoutTests(TestCase):

    def setUp(self):
        self.sar, _ = Currency.objects.get_or_create(code='SAR', defaults={'name': 'SAR', 'symbol': 'ر.س'})
        self.company = Company.objects.create(name='SessCo', currency=self.sar, country_code='SA')
        self.user = CustomUser.objects.create_user(
            email='sess@example.com', password='Strong-Sess-1234!', company=self.company.name,
        )
        policy = CompanySecurityPolicy.for_company(self.company)
        policy.session_timeout_minutes = 15  # very short for test
        policy.save()
        self._wh = _mute_webhooks(); self._wh.start()

    def tearDown(self):
        self._wh.stop()

    def test_per_tenant_timeout_applied(self):
        self.client.force_login(self.user)
        # Trigger middleware
        self.client.get('/realtime/wallboard/')
        # Session expiry is set to 15 min = 900s (within tolerance)
        from django.contrib.sessions.models import Session
        sess = Session.objects.get(session_key=self.client.session.session_key)
        # expire_date - now should be ~15 min
        from django.utils import timezone
        seconds = (sess.expire_date - timezone.now()).total_seconds()
        self.assertGreater(seconds, 14 * 60)
        self.assertLess(seconds, 16 * 60)
