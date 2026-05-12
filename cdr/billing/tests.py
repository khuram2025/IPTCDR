"""Fraud evaluator coverage — one test per rule type + auto-disable side-effect."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import Company, Currency, Extension
from cdr3cx.models import CallRecord

from .models import FraudIncident, FraudRule
from .services.country import iso_country
from .services.fraud import evaluate_call


def _mute_webhooks():
    """The api app emits webhooks on CallRecord/FraudIncident save; mute the
    network call so we don't depend on requests reaching example.invalid."""
    return patch('api.services.webhooks.requests.post', return_value=type(
        'R', (), {'status_code': 200, 'text': 'OK'})())


class CountryResolverTests(TestCase):

    def test_e164_resolves(self):
        self.assertEqual(iso_country('+966501234567'), 'SA')
        self.assertEqual(iso_country('+18005551234'), 'US')
        self.assertEqual(iso_country('+201000000000'), 'EG')

    def test_local_saudi_mobile(self):
        self.assertEqual(iso_country('0501234567'), 'SA')
        self.assertEqual(iso_country('501234567'), 'SA')

    def test_internal_extension_returns_none(self):
        self.assertIsNone(iso_country('1234'))

    def test_empty_returns_none(self):
        self.assertIsNone(iso_country(''))
        self.assertIsNone(iso_country(None))


class _FraudTestBase(TestCase):
    """Shared fixtures for evaluator tests."""

    def setUp(self):
        self.sar, _ = Currency.objects.get_or_create(
            code='SAR', defaults={'name': 'Saudi Riyal', 'symbol': 'ر.س'},
        )
        self.company = Company.objects.create(
            name='FraudCo', currency=self.sar, country_code='SA',
        )
        self.now = timezone.now().replace(microsecond=0)
        # Disable any default seeded rules (test isolation)
        FraudRule.objects.filter(company=self.company).delete()
        # Default: webhooks muted so signal fan-out doesn't hit network
        self._wh_patcher = _mute_webhooks()
        self._wh_patcher.start()

    def tearDown(self):
        self._wh_patcher.stop()

    def _rule(self, rule_type, threshold, **kw):
        defaults = dict(
            company=self.company, name=f'test {rule_type}', rule_type=rule_type,
            threshold=Decimal(str(threshold)), time_window_minutes=60,
            severity='high', action='alert', shadow_mode=False, is_active=True,
        )
        defaults.update(kw)
        return FraudRule.objects.create(**defaults)

    def _call(self, **kw):
        defaults = dict(
            company=self.company, source_pbx='3cx', caller='2001', callee='+18005551234',
            duration=60, call_time=self.now, total_cost=Decimal('0'),
        )
        defaults.update(kw)
        return CallRecord.objects.create(**defaults)


class IntlSpikeRuleTests(_FraudTestBase):

    def test_triggers_when_threshold_reached(self):
        self._rule('intl_spike', threshold=2, time_window_minutes=60)
        # First two calls accumulate; third triggers (count >= 2)
        self._call(callee='+18005551234', call_time=self.now - timedelta(minutes=10))
        self._call(callee='+18005551235', call_time=self.now - timedelta(minutes=5))
        FraudIncident.objects.all().delete()  # reset incidents from previous saves
        self._call(callee='+18005551236', call_time=self.now)
        self.assertEqual(
            FraudIncident.objects.filter(rule__rule_type='intl_spike').count(), 1,
        )

    def test_local_calls_dont_trigger(self):
        self._rule('intl_spike', threshold=1)
        self._call(callee='0501234567')
        self.assertFalse(FraudIncident.objects.filter(rule__rule_type='intl_spike').exists())


class PremiumDestinationRuleTests(_FraudTestBase):

    def test_blacklisted_country_triggers(self):
        self._rule('premium_destination', threshold=1, countries=['CU', 'KP'])
        self._call(callee='+5355551234')  # Cuba
        self.assertEqual(
            FraudIncident.objects.filter(rule__rule_type='premium_destination').count(), 1,
        )

    def test_other_country_does_not_trigger(self):
        self._rule('premium_destination', threshold=1, countries=['CU'])
        self._call(callee='+18005551234')  # US
        self.assertFalse(
            FraudIncident.objects.filter(rule__rule_type='premium_destination').exists(),
        )


class VelocityRulesTests(_FraudTestBase):

    def test_velocity_calls_triggers_at_threshold(self):
        self._rule('velocity_calls', threshold=3, time_window_minutes=60)
        for i in range(2):
            self._call(call_time=self.now - timedelta(minutes=20 - i))
        FraudIncident.objects.all().delete()
        self._call(call_time=self.now)
        self.assertTrue(FraudIncident.objects.filter(rule__rule_type='velocity_calls').exists())

    def test_velocity_cost_triggers_at_threshold(self):
        # CallRecord.save() runs categorize_call() which overrides call_rate
        # from CallPattern. Seed a high intl rate so two 1-min calls > 200.
        from cdr3cx.models import CallPattern
        CallPattern.objects.create(
            company=self.company, name='intl', pattern='+',
            call_type='international', rate_per_min=Decimal('150'),
        )
        self._rule('velocity_cost', threshold=200)
        self._call(callee='+18005551234', duration=60,
                   call_time=self.now - timedelta(minutes=5))
        FraudIncident.objects.all().delete()
        self._call(callee='+18005551235', duration=60, call_time=self.now)
        self.assertTrue(FraudIncident.objects.filter(rule__rule_type='velocity_cost').exists())

    def test_velocity_duration_triggers(self):
        self._rule('velocity_duration', threshold=300)
        self._call(duration=120, call_time=self.now - timedelta(minutes=10))
        FraudIncident.objects.all().delete()
        self._call(duration=200, call_time=self.now)
        self.assertTrue(FraudIncident.objects.filter(rule__rule_type='velocity_duration').exists())


class LongIntlRuleTests(_FraudTestBase):

    def test_long_intl_triggers(self):
        self._rule('long_intl', threshold=1800)  # 30 min
        self._call(callee='+18005551234', duration=2000)
        self.assertTrue(FraudIncident.objects.filter(rule__rule_type='long_intl').exists())

    def test_short_call_does_not(self):
        self._rule('long_intl', threshold=1800)
        self._call(callee='+18005551234', duration=120)
        self.assertFalse(FraudIncident.objects.filter(rule__rule_type='long_intl').exists())


class AutoDisableActionTests(_FraudTestBase):

    def test_critical_rule_disables_extension_when_not_in_shadow(self):
        ext = Extension.objects.create(
            extension='2001', company=self.company, full_name='Test Agent',
            disable_external_call=False,
        )
        self._rule('long_intl', threshold=60, severity='critical',
                   action='disable_extension', shadow_mode=False)
        self._call(callee='+18005551234', duration=120)
        ext.refresh_from_db()
        self.assertTrue(ext.disable_external_call)
        incident = FraudIncident.objects.first()
        self.assertEqual(incident.action_executed, 'disable_extension')

    def test_shadow_mode_does_not_disable(self):
        ext = Extension.objects.create(
            extension='2001', company=self.company, full_name='Test Agent',
            disable_external_call=False,
        )
        self._rule('long_intl', threshold=60, action='disable_extension', shadow_mode=True)
        self._call(callee='+18005551234', duration=120)
        ext.refresh_from_db()
        self.assertFalse(ext.disable_external_call)
        incident = FraudIncident.objects.first()
        self.assertEqual(incident.action_executed, 'shadow')


class SignalIntegrationTests(_FraudTestBase):

    def test_signal_creates_incident_automatically(self):
        self._rule('long_intl', threshold=60)
        # Just save a CDR — signal handler should run evaluator
        self._call(callee='+18005551234', duration=120)
        self.assertEqual(FraudIncident.objects.count(), 1)

    def test_inactive_rule_skipped(self):
        self._rule('long_intl', threshold=60, is_active=False)
        self._call(callee='+18005551234', duration=120)
        self.assertEqual(FraudIncident.objects.count(), 0)


class FraudAuditReportTests(TestCase):
    """Free toll-fraud audit (lead-gen) — CSV → analysis → PDF."""

    def _sample_csv(self) -> bytes:
        # Mix: clean local, premium destination, after-hours intl, long intl
        return (
            "call_time,caller,callee,duration,total_cost\n"
            "2026-04-01 10:00:00,2001,0501234567,60,0.50\n"            # local OK
            "2026-04-01 10:30:00,2001,+18005551234,300,5.00\n"          # US ok
            "2026-04-01 23:45:00,2002,+18005551234,90,2.00\n"           # after hours intl
            "2026-04-02 02:30:00,2003,+5355551234,1900,80.00\n"         # CU long intl + after hours + premium
            "2026-04-02 03:00:00,2003,+8505551234,2100,90.00\n"         # KP after hours + premium
            "2026-04-02 09:00:00,2099,+18005551234,30,0.20\n"
        ).encode('utf-8')

    def test_parse_cdr_csv(self):
        from io import BytesIO
        from billing.services.audit_report import parse_cdr_csv
        rows = parse_cdr_csv(BytesIO(self._sample_csv()))
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]['caller'], '2001')

    def test_analyze_surfaces_known_findings(self):
        from io import BytesIO
        from billing.services.audit_report import analyze, parse_cdr_csv
        report = analyze(parse_cdr_csv(BytesIO(self._sample_csv())))
        finding_titles = [f['title'] for f in report['findings']]
        # We expect at minimum: premium, after-hours intl, long intl
        self.assertTrue(any('premium' in t.lower() for t in finding_titles), finding_titles)
        self.assertTrue(any('after-hours' in t.lower() for t in finding_titles), finding_titles)
        self.assertTrue(any('long' in t.lower() for t in finding_titles), finding_titles)
        self.assertEqual(report['summary']['total_calls'], 6)
        self.assertGreater(report['summary']['intl_calls'], 0)

    def test_render_pdf_returns_valid_pdf(self):
        from io import BytesIO
        from billing.services.audit_report import analyze, parse_cdr_csv, render_pdf
        report = analyze(parse_cdr_csv(BytesIO(self._sample_csv())))
        pdf = render_pdf(report, contact_name='Khalid', contact_company='AcmeBank')
        self.assertTrue(pdf.startswith(b'%PDF'))
        # Reasonable size — not empty, not insane
        self.assertGreater(len(pdf), 2000)

    def test_view_returns_pdf_response(self):
        from io import BytesIO
        from django.test import Client
        client = Client()
        # GET shows the form
        r = client.get('/billing/free-fraud-audit/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Free Toll-Fraud Audit', r.content)
        # POST returns a PDF
        r = client.post('/billing/free-fraud-audit/', {
            'contact_name': 'Khalid',
            'contact_company': 'AcmeBank',
            'contact_email': 'k@example.com',
            'cdr_csv': BytesIO(self._sample_csv()).read() and __import__('django').core.files.uploadedfile.SimpleUploadedFile(
                'sample.csv', self._sample_csv(), content_type='text/csv',
            ),
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_view_rejects_empty_upload(self):
        from django.test import Client
        client = Client()
        r = client.post('/billing/free-fraud-audit/', {
            'contact_name': 'Khalid', 'contact_company': 'Acme',
            'contact_email': 'k@example.com',
        })
        self.assertEqual(r.status_code, 200)  # re-renders form with error
        self.assertIn(b'Please attach', r.content)
