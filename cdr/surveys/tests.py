"""Survey ingest and linking tests."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from accounts.models import Company
from cdr3cx.models import CallRecord
from surveys.models import SurveyCampaign, SurveyQuestion, SurveyQuestionOption
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

    def test_option_digit_maps_to_score(self):
        """A configured digit→score option drives the recorded numeric value."""
        rating_q = self.campaign.questions.get(tag='rating')
        # Press digit 3, but configure it to mean "Excellent" worth 5 points.
        SurveyQuestionOption.objects.create(
            question=rating_q, order=1, digit='3', label='Excellent', score=5,
        )
        resp, _ = ingest_survey_response(self.campaign, {
            'caller': '966502222222',
            'completed_at': timezone.now().isoformat(),
            'answers': [{'tag': 'rating', 'value': '3'}],
        })
        ans = resp.answers.get(tag='rating')
        self.assertEqual(ans.value_numeric, 5)
        self.assertEqual(ans.value_text, 'Excellent')

    def test_option_yes_no_score(self):
        solved_q = self.campaign.questions.get(tag='solved')
        SurveyQuestionOption.objects.create(question=solved_q, order=1, digit='1', label='Yes', score=1)
        SurveyQuestionOption.objects.create(question=solved_q, order=2, digit='2', label='No', score=0)
        resp, _ = ingest_survey_response(self.campaign, {
            'caller': '966503333333',
            'completed_at': timezone.now().isoformat(),
            'answers': [{'tag': 'solved', 'value': '2'}],
        })
        ans = resp.answers.get(tag='solved')
        self.assertFalse(ans.value_bool)
        self.assertEqual(ans.value_text, 'No')


class SurveyQuestionCrudTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='CRUD Co', survey_enabled=True, survey_cfd_verified=True,
        )
        self.admin = self._make_user('admin@crud.co', 'company_admin')
        self.client = Client()
        self.client.force_login(self.admin)

    def _make_user(self, email, role):
        user = get_user_model()(email=email, company=self.company, role=role)
        user.set_password('pw12345')
        user.save()
        return user

    def test_pages_render(self):
        self.assertEqual(self.client.get(reverse('surveys:settings')).status_code, 200)
        self.assertEqual(self.client.get(reverse('surveys:question_add')).status_code, 200)
        camp = SurveyCampaign.objects.create(company=self.company, name='C', slug='c')
        q = SurveyQuestion.objects.create(campaign=camp, order=1, tag='solved', question_type='yes_no')
        self.assertEqual(self.client.get(reverse('surveys:question_edit', args=[q.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('surveys:question_delete', args=[q.pk])).status_code, 200)

    def test_add_question_with_options(self):
        resp = self.client.post(reverse('surveys:question_add'), {
            'order': 1, 'tag': 'rating', 'question_type': 'range',
            'prompt_text': 'Rate 1-3', 'min_value': 1, 'max_value': 3, 'required': 'on',
            'options-TOTAL_FORMS': '2', 'options-INITIAL_FORMS': '0',
            'options-MIN_NUM_FORMS': '0', 'options-MAX_NUM_FORMS': '1000',
            'options-0-order': '1', 'options-0-digit': '1', 'options-0-label': 'Bad', 'options-0-score': '1',
            'options-1-order': '2', 'options-1-digit': '3', 'options-1-label': 'Great', 'options-1-score': '3',
        })
        self.assertEqual(resp.status_code, 302)
        q = SurveyQuestion.objects.get(campaign__company=self.company, tag='rating')
        self.assertEqual(q.options.count(), 2)
        self.assertEqual(q.options.get(digit='3').label, 'Great')

    def test_delete_question(self):
        camp = SurveyCampaign.objects.create(company=self.company, name='C', slug='c')
        q = SurveyQuestion.objects.create(campaign=camp, order=1, tag='solved', question_type='yes_no')
        resp = self.client.post(reverse('surveys:question_delete', args=[q.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(SurveyQuestion.objects.filter(pk=q.pk).exists())

    def test_non_admin_blocked(self):
        viewer = self._make_user('viewer@crud.co', 'user')
        c = Client()
        c.force_login(viewer)
        resp = c.get(reverse('surveys:question_add'))
        self.assertEqual(resp.status_code, 404)
