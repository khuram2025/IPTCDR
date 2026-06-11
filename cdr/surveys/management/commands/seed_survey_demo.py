"""Seed a demo survey campaign for E2E / pilot verification."""
from django.core.management.base import BaseCommand

from accounts.models import Company
from surveys.models import SurveyCampaign, SurveyQuestion


class Command(BaseCommand):
    help = 'Enable surveys and create default CSAT campaign for a company (pilot).'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)

    def handle(self, *args, **options):
        company = Company.objects.get(pk=options['company_id'])
        company.survey_enabled = True
        company.survey_cfd_verified = True
        company.save(update_fields=['survey_enabled', 'survey_cfd_verified'])

        camp, created = SurveyCampaign.objects.get_or_create(
            company=company,
            slug='post-call-csat',
            defaults={
                'name': 'Post-Call CSAT',
                'license_verified': True,
                'cfd_app_name': 'ZentrycPostCallSurvey',
            },
        )
        if created:
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
        self.stdout.write(self.style.SUCCESS(
            f'Campaign {camp.slug} ready. Token: {camp.ingest_token}'
        ))
