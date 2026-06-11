from django.contrib import admin

from .models import (
    SurveyAnswer, SurveyCampaign, SurveyDailyRollup, SurveyQuestion, SurveyResponse,
)


class SurveyQuestionInline(admin.TabularInline):
    model = SurveyQuestion
    extra = 0


@admin.register(SurveyCampaign)
class SurveyCampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'slug', 'license_verified', 'is_active')
    list_filter = ('license_verified', 'is_active', 'company')
    search_fields = ('name', 'slug', 'company__name')
    inlines = [SurveyQuestionInline]
    readonly_fields = ('ingest_token', 'created_at', 'updated_at')


@admin.register(SurveyResponse)
class SurveyResponseAdmin(admin.ModelAdmin):
    list_display = ('caller', 'company', 'campaign', 'completed_at', 'match_confidence')
    list_filter = ('match_confidence', 'company')
    search_fields = ('caller',)
    readonly_fields = ('raw_payload', 'idempotency_key', 'created_at')


@admin.register(SurveyDailyRollup)
class SurveyDailyRollupAdmin(admin.ModelAdmin):
    list_display = ('company', 'stat_date', 'response_count', 'csat_pct', 'nps_score')
    list_filter = ('company',)
