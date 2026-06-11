"""Post-call IVR survey models (3CX CFD integration)."""
import secrets

from django.db import models
from django.utils.text import slugify


def _generate_ingest_token() -> str:
    return secrets.token_urlsafe(32)


class SurveyCampaign(models.Model):
    CHANNEL_IVR_CFD = 'ivr_cfd'
    CHANNEL_CHOICES = [(CHANNEL_IVR_CFD, 'IVR (3CX Call Flow Designer)')]

    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='survey_campaigns',
    )
    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=64)
    channel = models.CharField(max_length=16, choices=CHANNEL_CHOICES, default=CHANNEL_IVR_CFD)
    cfd_app_name = models.CharField(max_length=128, blank=True, default='')
    intro_audio_url = models.URLField(max_length=512, blank=True, default='')
    goodbye_audio_url = models.URLField(max_length=512, blank=True, default='')
    license_verified = models.BooleanField(
        default=False,
        help_text='Tenant confirmed 3CX Call Flow Apps / CFD license.',
    )
    license_note = models.CharField(max_length=255, blank=True, default='')
    ingest_token = models.CharField(max_length=64, default=_generate_ingest_token, unique=True)
    match_window_minutes = models.PositiveIntegerField(default=30)
    csat_target_pct = models.PositiveIntegerField(default=80)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('company', 'slug')
        ordering = ['company', 'name']

    def __str__(self):
        return f'{self.company.name} — {self.name}'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or 'campaign'
            slug = base
            n = 1
            while SurveyCampaign.objects.filter(company=self.company, slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def regenerate_token(self):
        self.ingest_token = _generate_ingest_token()
        self.save(update_fields=['ingest_token', 'updated_at'])
        return self.ingest_token


class SurveyQuestion(models.Model):
    TYPE_YES_NO = 'yes_no'
    TYPE_RANGE = 'range'
    TYPE_NPS = 'nps'
    TYPE_RECORDING = 'recording'
    TYPE_SINGLE_DIGIT = 'single_digit'
    TYPE_CHOICES = [
        (TYPE_YES_NO, 'Yes / No'),
        (TYPE_RANGE, 'Numeric range'),
        (TYPE_NPS, 'NPS (0–10)'),
        (TYPE_RECORDING, 'Voice recording'),
        (TYPE_SINGLE_DIGIT, 'Single digit'),
    ]

    campaign = models.ForeignKey(SurveyCampaign, on_delete=models.CASCADE, related_name='questions')
    order = models.PositiveSmallIntegerField(default=1)
    tag = models.CharField(max_length=32, help_text='CFD Survey component tag, e.g. solved, rating')
    question_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=TYPE_RANGE)
    prompt_text = models.TextField(blank=True, default='')
    min_value = models.IntegerField(null=True, blank=True)
    max_value = models.IntegerField(null=True, blank=True)
    required = models.BooleanField(default=True)

    class Meta:
        ordering = ['campaign', 'order']
        unique_together = ('campaign', 'tag')

    def __str__(self):
        return f'{self.campaign.slug}:{self.tag}'


class SurveyResponse(models.Model):
    MATCH_EXACT = 'exact'
    MATCH_HEURISTIC = 'heuristic'
    MATCH_UNMATCHED = 'unmatched'
    MATCH_CHOICES = [
        (MATCH_EXACT, 'Exact (call_record_id provided)'),
        (MATCH_HEURISTIC, 'Heuristic (caller + time window)'),
        (MATCH_UNMATCHED, 'Unmatched'),
    ]

    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='survey_responses',
    )
    campaign = models.ForeignKey(SurveyCampaign, on_delete=models.CASCADE, related_name='responses')
    caller = models.CharField(max_length=32, db_index=True)
    completed_at = models.DateTimeField(db_index=True)
    call_record = models.ForeignKey(
        'cdr3cx.CallRecord', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='survey_responses',
    )
    agent = models.ForeignKey(
        'acd.Agent', null=True, blank=True, on_delete=models.SET_NULL, related_name='survey_responses',
    )
    queue = models.ForeignKey(
        'acd.Queue', null=True, blank=True, on_delete=models.SET_NULL, related_name='survey_responses',
    )
    match_confidence = models.CharField(max_length=16, choices=MATCH_CHOICES, default=MATCH_UNMATCHED)
    source_pbx = models.CharField(max_length=20, default='3cx')
    idempotency_key = models.CharField(max_length=64, unique=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    recording_path = models.CharField(max_length=512, blank=True, default='')
    agent_dn_hint = models.CharField(max_length=32, blank=True, default='')
    queue_dn_hint = models.CharField(max_length=32, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-completed_at']
        indexes = [
            models.Index(fields=['company', '-completed_at']),
            models.Index(fields=['company', 'caller', '-completed_at']),
            models.Index(fields=['call_record']),
        ]

    def __str__(self):
        return f'Survey {self.caller} @ {self.completed_at:%Y-%m-%d %H:%M}'


class SurveyAnswer(models.Model):
    response = models.ForeignKey(SurveyResponse, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(
        SurveyQuestion, null=True, blank=True, on_delete=models.SET_NULL, related_name='answers',
    )
    tag = models.CharField(max_length=32)
    value_text = models.TextField(blank=True, default='')
    value_numeric = models.FloatField(null=True, blank=True)
    value_bool = models.BooleanField(null=True, blank=True)
    recording_path = models.CharField(max_length=512, blank=True, default='')

    class Meta:
        ordering = ['response', 'id']
        indexes = [models.Index(fields=['response', 'tag'])]

    def __str__(self):
        return f'{self.tag}={self.value_text or self.value_numeric}'


class SurveyDailyRollup(models.Model):
    """Materialized daily CSAT/NPS aggregates for fast dashboards."""
    company = models.ForeignKey(
        'accounts.Company', on_delete=models.CASCADE, related_name='survey_rollups',
    )
    stat_date = models.DateField(db_index=True)
    campaign = models.ForeignKey(
        SurveyCampaign, null=True, blank=True, on_delete=models.CASCADE, related_name='daily_rollups',
    )
    queue = models.ForeignKey(
        'acd.Queue', null=True, blank=True, on_delete=models.CASCADE, related_name='survey_rollups',
    )
    agent = models.ForeignKey(
        'acd.Agent', null=True, blank=True, on_delete=models.CASCADE, related_name='survey_rollups',
    )
    response_count = models.PositiveIntegerField(default=0)
    rating_count = models.PositiveIntegerField(default=0)
    rating_sum = models.FloatField(default=0)
    csat_topbox_count = models.PositiveIntegerField(default=0)
    solved_yes_count = models.PositiveIntegerField(default=0)
    solved_total_count = models.PositiveIntegerField(default=0)
    nps_promoters = models.PositiveIntegerField(default=0)
    nps_detractors = models.PositiveIntegerField(default=0)
    nps_total = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('company', 'stat_date', 'campaign', 'queue', 'agent')
        ordering = ['-stat_date']
        indexes = [models.Index(fields=['company', '-stat_date'])]

    @property
    def csat_pct(self):
        if not self.rating_count:
            return None
        return round(self.csat_topbox_count / self.rating_count * 100, 1)

    @property
    def avg_rating(self):
        if not self.rating_count:
            return None
        return round(self.rating_sum / self.rating_count, 2)

    @property
    def nps_score(self):
        if not self.nps_total:
            return None
        return round((self.nps_promoters - self.nps_detractors) / self.nps_total * 100, 1)

    def __str__(self):
        scope = self.queue or self.agent or self.campaign or 'company'
        return f'{self.company.name} {self.stat_date} {scope}'
