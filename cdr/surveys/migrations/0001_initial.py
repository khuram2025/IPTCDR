import surveys.models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0017_company_survey_flags'),
        ('acd', '0008_alter_scheduledreport_report_type_survey'),
        ('cdr3cx', '0016_userquota_is_blocked'),
    ]

    operations = [
        migrations.CreateModel(
            name='SurveyCampaign',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('slug', models.SlugField(max_length=64)),
                ('channel', models.CharField(choices=[('ivr_cfd', 'IVR (3CX Call Flow Designer)')], default='ivr_cfd', max_length=16)),
                ('cfd_app_name', models.CharField(blank=True, default='', max_length=128)),
                ('intro_audio_url', models.URLField(blank=True, default='', max_length=512)),
                ('goodbye_audio_url', models.URLField(blank=True, default='', max_length=512)),
                ('license_verified', models.BooleanField(default=False, help_text='Tenant confirmed 3CX Call Flow Apps / CFD license.')),
                ('license_note', models.CharField(blank=True, default='', max_length=255)),
                ('ingest_token', models.CharField(default=surveys.models._generate_ingest_token, max_length=64, unique=True)),
                ('match_window_minutes', models.PositiveIntegerField(default=30)),
                ('csat_target_pct', models.PositiveIntegerField(default=80)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='survey_campaigns', to='accounts.company')),
            ],
            options={
                'ordering': ['company', 'name'],
                'unique_together': {('company', 'slug')},
            },
        ),
        migrations.CreateModel(
            name='SurveyQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveSmallIntegerField(default=1)),
                ('tag', models.CharField(help_text='CFD Survey component tag, e.g. solved, rating', max_length=32)),
                ('question_type', models.CharField(choices=[('yes_no', 'Yes / No'), ('range', 'Numeric range'), ('nps', 'NPS (0–10)'), ('recording', 'Voice recording'), ('single_digit', 'Single digit')], default='range', max_length=16)),
                ('prompt_text', models.TextField(blank=True, default='')),
                ('min_value', models.IntegerField(blank=True, null=True)),
                ('max_value', models.IntegerField(blank=True, null=True)),
                ('required', models.BooleanField(default=True)),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='surveys.surveycampaign')),
            ],
            options={
                'ordering': ['campaign', 'order'],
                'unique_together': {('campaign', 'tag')},
            },
        ),
        migrations.CreateModel(
            name='SurveyResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('caller', models.CharField(db_index=True, max_length=32)),
                ('completed_at', models.DateTimeField(db_index=True)),
                ('match_confidence', models.CharField(choices=[('exact', 'Exact (call_record_id provided)'), ('heuristic', 'Heuristic (caller + time window)'), ('unmatched', 'Unmatched')], default='unmatched', max_length=16)),
                ('source_pbx', models.CharField(default='3cx', max_length=20)),
                ('idempotency_key', models.CharField(max_length=64, unique=True)),
                ('raw_payload', models.JSONField(blank=True, default=dict)),
                ('recording_path', models.CharField(blank=True, default='', max_length=512)),
                ('agent_dn_hint', models.CharField(blank=True, default='', max_length=32)),
                ('queue_dn_hint', models.CharField(blank=True, default='', max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('agent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='survey_responses', to='acd.agent')),
                ('call_record', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='survey_responses', to='cdr3cx.callrecord')),
                ('campaign', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='responses', to='surveys.surveycampaign')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='survey_responses', to='accounts.company')),
                ('queue', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='survey_responses', to='acd.queue')),
            ],
            options={
                'ordering': ['-completed_at'],
            },
        ),
        migrations.CreateModel(
            name='SurveyAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tag', models.CharField(max_length=32)),
                ('value_text', models.TextField(blank=True, default='')),
                ('value_numeric', models.FloatField(blank=True, null=True)),
                ('value_bool', models.BooleanField(blank=True, null=True)),
                ('recording_path', models.CharField(blank=True, default='', max_length=512)),
                ('question', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='answers', to='surveys.surveyquestion')),
                ('response', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='surveys.surveyresponse')),
            ],
            options={
                'ordering': ['response', 'id'],
            },
        ),
        migrations.CreateModel(
            name='SurveyDailyRollup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stat_date', models.DateField(db_index=True)),
                ('response_count', models.PositiveIntegerField(default=0)),
                ('rating_count', models.PositiveIntegerField(default=0)),
                ('rating_sum', models.FloatField(default=0)),
                ('csat_topbox_count', models.PositiveIntegerField(default=0)),
                ('solved_yes_count', models.PositiveIntegerField(default=0)),
                ('solved_total_count', models.PositiveIntegerField(default=0)),
                ('nps_promoters', models.PositiveIntegerField(default=0)),
                ('nps_detractors', models.PositiveIntegerField(default=0)),
                ('nps_total', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('agent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='survey_rollups', to='acd.agent')),
                ('campaign', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='daily_rollups', to='surveys.surveycampaign')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='survey_rollups', to='accounts.company')),
                ('queue', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='survey_rollups', to='acd.queue')),
            ],
            options={
                'ordering': ['-stat_date'],
                'unique_together': {('company', 'stat_date', 'campaign', 'queue', 'agent')},
            },
        ),
        migrations.AddIndex(
            model_name='surveyresponse',
            index=models.Index(fields=['company', '-completed_at'], name='surveys_sur_company_6a8f2d_idx'),
        ),
        migrations.AddIndex(
            model_name='surveyresponse',
            index=models.Index(fields=['company', 'caller', '-completed_at'], name='surveys_sur_company_caller_idx'),
        ),
        migrations.AddIndex(
            model_name='surveyresponse',
            index=models.Index(fields=['call_record'], name='surveys_sur_call_re_idx'),
        ),
        migrations.AddIndex(
            model_name='surveyanswer',
            index=models.Index(fields=['response', 'tag'], name='surveys_sur_response_tag_idx'),
        ),
        migrations.AddIndex(
            model_name='surveydailyrollup',
            index=models.Index(fields=['company', '-stat_date'], name='surveys_sur_company_stat_idx'),
        ),
    ]
