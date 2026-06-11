"""Survey ingest and linking tests."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import Company
from cdr3cx.models import CallRecord
from surveys.models import SurveyCampaign, SurveyQuestion
from surveys.services.ingest import IngestError, ingest_survey_response, resolve_campaign_from_token
from surveys.services.linking import link_call_record


class SurveyIngestTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='Survey Test Co',
            survey_enabled=True,
            survey_cfd_verified=True,
        )
        self.campaign = SurveyCampaign.objects.create(
            company=self.company,
            name='Post-Call CSAT',
            slug='post-call-csat',
            license_verified=True,
        )
        SurveyQuestion.objects.create(
            campaign=self.campaign, order=1, tag='solved', question_type='yes_no',
        )
        SurveyQuestion.objects.create(
            campaign=self.campaign, order=2, tag='rating', question_type='range',
            min_value=1, max_value=5,
        )

    def test_ingest_and_link(self):
        now = timezone.now()
        CallRecord.objects.create(
            company=self.company,
            caller='966501234567',
            from_no='966501234567',
            callee='100',
            call_time=now - timedelta(minutes=5),
            time_answered=now - timedelta(minutes=4),
            time_end=now - timedelta(minutes=1),
            duration=180,
            final_dn='101',
        )
        payload = {
            'caller': '966501234567',
            'completed_at': now.isoformat(),
            'agent_dn': '101',
            'answers': [
                {'tag': 'solved', 'value': 'YES'},
                {'tag': 'rating', 'value': '5'},
            ],
        }
        resp, created = ingest_survey_response(self.campaign, payload)
        self.assertTrue(created)
        self.assertIsNotNone(resp.call_record_id)
        self.assertEqual(resp.match_confidence, 'heuristic')

    def test_idempotency(self):
        ts = timezone.now().isoformat()
        payload = {
            'caller': '966509999999',
            'completed_at': ts,
            'answers': [{'tag': 'rating', 'value': '4'}],
        }
        _, c1 = ingest_survey_response(self.campaign, payload)
        _, c2 = ingest_survey_response(self.campaign, payload)
        self.assertTrue(c1)
        self.assertFalse(c2)

    def test_license_gate(self):
        self.campaign.license_verified = False
        self.campaign.save()
        with self.assertRaises(IngestError) as ctx:
            ingest_survey_response(self.campaign, {'caller': '123', 'answers': []})
        self.assertEqual(ctx.exception.status_code, 403)

    def test_token_resolve(self):
        camp = resolve_campaign_from_token(self.campaign.ingest_token)
        self.assertEqual(camp.pk, self.campaign.pk)

    def test_exact_link(self):
        rec = CallRecord.objects.create(
            company=self.company, caller='100', call_time=timezone.now(), duration=60,
        )
        linked, _, _, match = link_call_record(
            self.company, '100', timezone.now(), call_record_id=rec.pk,
        )
        self.assertEqual(linked.pk, rec.pk)
        self.assertEqual(match, 'exact')

    def test_ingest_api_endpoint(self):
        import json
        from django.test import Client
        client = Client()
        payload = {
            'campaign_slug': 'post-call-csat',
            'caller': '966501111111',
            'answers': [{'tag': 'rating', 'value': '5'}],
        }
        resp = client.post(
            '/api/v1/survey-responses/ingest/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_SURVEY_TOKEN=self.campaign.ingest_token,
            HTTP_HOST='localhost',
        )
        self.assertIn(resp.status_code, (200, 201))
        self.assertTrue(resp.json()['created'])
