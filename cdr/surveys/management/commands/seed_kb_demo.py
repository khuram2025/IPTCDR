"""Seed Zentryc-branded demo tenant for public KB screenshots."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Company
from surveys.models import SurveyCampaign, SurveyQuestion, SurveyResponse
from surveys.services.ingest import ingest_survey_response
from surveys.tasks import compute_survey_daily_rollups

DEMO_EMAIL = 'demo@zentryc.com'
DEMO_PASSWORD = 'Zentryc@Demo2026'
DEMO_TOKEN = 'Zentryc-DEMO-TOKEN-REPLACE-WITH-YOUR-OWN'


class Command(BaseCommand):
    help = 'Create Zentryc demo company, user and sample survey data for KB screenshots.'

    def handle(self, *args, **options):
        User = get_user_model()
        company, _ = Company.objects.get_or_create(
            name='Zentryc',
            defaults={'country_code': 'SA'},
        )
        company.survey_enabled = True
        company.survey_cfd_verified = True
        company.save(update_fields=['survey_enabled', 'survey_cfd_verified'])

        user, created = User.objects.get_or_create(
            email=DEMO_EMAIL,
            defaults={
                'company': company,
                'role': 'company_admin',
                'is_active': True,
            },
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
        elif user.company_id != company.id:
            user.company = company
            user.role = 'company_admin'
            user.save(update_fields=['company', 'role'])

        camp, camp_created = SurveyCampaign.objects.get_or_create(
            company=company,
            slug='post-call-csat',
            defaults={
                'name': 'Post-Call CSAT',
                'license_verified': True,
                'cfd_app_name': 'ZentrycPostCallSurvey',
                'ingest_token': DEMO_TOKEN,
            },
        )
        if not camp_created and camp.ingest_token != DEMO_TOKEN:
            camp.ingest_token = DEMO_TOKEN
            camp.save(update_fields=['ingest_token'])

        if camp_created or not camp.questions.exists():
            SurveyQuestion.objects.filter(campaign=camp).delete()
            SurveyQuestion.objects.bulk_create([
                SurveyQuestion(
                    campaign=camp, order=1, tag='solved', question_type='yes_no',
                    prompt_text='Have we resolved the issue you called about?',
                ),
                SurveyQuestion(
                    campaign=camp, order=2, tag='rating', question_type='range',
                    prompt_text='Rate the attention received (1–5).', min_value=1, max_value=5,
                ),
                SurveyQuestion(
                    campaign=camp, order=3, tag='comments', question_type='recording',
                    prompt_text='Leave a voice comment.', required=False,
                ),
            ])

        # Replace prior demo responses with fresh anonymized samples.
        SurveyResponse.objects.filter(company=company).delete()
        now = timezone.now()
        samples = [
            ('966500000001', 5, 'YES', 101, '800'),
            ('966500000002', 4, 'YES', 102, '800'),
            ('966500000003', 5, 'YES', 101, '801'),
            ('966500000004', 3, 'NO', 103, '800'),
            ('966500000005', 5, 'YES', 102, '801'),
            ('966500000006', 4, 'YES', 101, '800'),
            ('966500000007', 2, 'NO', 103, '802'),
            ('966500000008', 5, 'YES', 102, '800'),
            ('966500000009', 4, 'YES', 101, '801'),
            ('966500000010', 5, 'YES', 102, '800'),
            ('966500000011', 3, 'NO', 103, '800'),
            ('966500000012', 5, 'YES', 101, '800'),
        ]
        for i, (caller, rating, solved, agent_dn, queue_dn) in enumerate(samples):
            completed = now - timedelta(hours=i * 6 + 1)
            ingest_survey_response(camp, {
                'caller': caller,
                'completed_at': completed.isoformat(),
                'agent_dn': str(agent_dn),
                'queue_dn': str(queue_dn),
                'answers': [
                    {'tag': 'solved', 'value': solved},
                    {'tag': 'rating', 'value': str(rating)},
                ],
            })

        compute_survey_daily_rollups(company_id=company.id, days_back=30)

        self.stdout.write(self.style.SUCCESS(
            f'KB demo ready: company={company.name} id={company.id} '
            f'user={DEMO_EMAIL} responses={len(samples)}'
        ))
