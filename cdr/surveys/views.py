"""Survey UI views (Velzon templates)."""
import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from surveys.forms import CompanySurveyFlagsForm, SurveyCampaignForm, SurveyQuestionFormSet
from surveys.models import SurveyCampaign, SurveyResponse
from surveys.services.metrics import survey_dashboard_metrics

from .forms import SurveyCampaignForm as _  # noqa: F401 — re-export for tests


def _require_surveys(request):
    company = getattr(request.user, 'company', None)
    if not company or not company.surveys_available:
        return None
    return company


def _parse_date_range(request):
    period = request.GET.get('period', '1m')
    now = timezone.now()
    end = now
    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == '7d':
        start = now - timedelta(days=7)
    elif period == '6m':
        start = now - timedelta(days=180)
    elif period == '1y':
        start = now - timedelta(days=365)
    else:
        start = now - timedelta(days=30)
    custom_start = request.GET.get('start')
    custom_end = request.GET.get('end')
    if custom_start and custom_end:
        try:
            start = timezone.make_aware(datetime.strptime(custom_start, '%Y-%m-%d'))
            end = timezone.make_aware(
                datetime.strptime(custom_end, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            )
        except ValueError:
            pass
    return start, end, timezone.localtime(start).date(), timezone.localtime(end).date()


@login_required
def survey_dashboard(request):
    company = _require_surveys(request)
    if not company:
        return render(request, 'surveys/unavailable.html', status=403)

    start_dt, end_dt, start_date, end_date = _parse_date_range(request)
    metrics = survey_dashboard_metrics(company, start_date, end_date)
    recent = (
        SurveyResponse.objects.filter(company=company, completed_at__range=(start_dt, end_dt))
        .select_related('campaign', 'agent', 'queue')
        .order_by('-completed_at')[:15]
    )

    return render(request, 'surveys/dashboard.html', {
        'metrics': metrics,
        'metrics_json': json.dumps(metrics, default=str),
        'recent_responses': recent,
        'start_date': start_date,
        'end_date': end_date,
        'period': request.GET.get('period', '1m'),
        'filter_base_url': reverse('surveys:dashboard'),
    })


@login_required
def survey_responses(request):
    company = _require_surveys(request)
    if not company:
        return render(request, 'surveys/unavailable.html', status=403)

    start_dt, end_dt, start_date, end_date = _parse_date_range(request)
    qs = (
        SurveyResponse.objects.filter(company=company, completed_at__range=(start_dt, end_dt))
        .select_related('campaign', 'agent', 'queue', 'call_record')
        .prefetch_related('answers')
        .order_by('-completed_at')
    )
    match = request.GET.get('match')
    if match:
        qs = qs.filter(match_confidence=match)

    return render(request, 'surveys/responses.html', {
        'responses': qs[:500],
        'start_date': start_date,
        'end_date': end_date,
        'period': request.GET.get('period', '1m'),
        'filter_base_url': reverse('surveys:responses'),
        'match_filter': match,
    })


@login_required
def survey_response_detail(request, pk):
    company = _require_surveys(request)
    if not company:
        return render(request, 'surveys/unavailable.html', status=403)

    resp = get_object_or_404(
        SurveyResponse.objects.select_related('campaign', 'agent', 'queue', 'call_record')
        .prefetch_related('answers'),
        pk=pk, company=company,
    )
    return render(request, 'surveys/response_detail.html', {'response': resp})


@login_required
def survey_settings(request):
    company = getattr(request.user, 'company', None)
    if not company:
        raise Http404
    if request.user.role not in ('company_admin', 'superadmin'):
        return render(request, 'surveys/unavailable.html', {
            'message': 'Only company administrators can manage survey settings.',
        }, status=403)

    flags_form = CompanySurveyFlagsForm(
        request.POST or None,
        initial={
            'survey_enabled': company.survey_enabled,
            'survey_cfd_verified': company.survey_cfd_verified,
        },
    )
    if request.method == 'POST' and 'save_flags' in request.POST and flags_form.is_valid():
        company.survey_enabled = flags_form.cleaned_data['survey_enabled']
        company.survey_cfd_verified = flags_form.cleaned_data['survey_cfd_verified']
        company.save(update_fields=['survey_enabled', 'survey_cfd_verified'])
        messages.success(request, 'Survey feature flags updated.')
        return redirect('surveys:settings')

    campaign = company.survey_campaigns.filter(is_active=True).first()
    campaign_form = None
    question_formset = None

    if request.method == 'POST' and 'save_campaign' in request.POST:
        campaign_form = SurveyCampaignForm(request.POST, instance=campaign)
        camp_instance = campaign if campaign and campaign.pk else SurveyCampaign(company=company)
        question_formset = SurveyQuestionFormSet(request.POST, instance=camp_instance)
        if campaign_form.is_valid() and question_formset.is_valid():
            camp = campaign_form.save(commit=False)
            camp.company = company
            if not camp.license_verified:
                camp.license_verified = company.survey_cfd_verified
            camp.save()
            question_formset.instance = camp
            question_formset.save()
            messages.success(request, 'Survey campaign saved.')
            return redirect('surveys:settings')
    else:
        if not campaign and company.survey_enabled:
            campaign = SurveyCampaign(
                company=company,
                name='Post-Call CSAT',
                license_verified=company.survey_cfd_verified,
            )
        campaign_form = SurveyCampaignForm(instance=campaign)
        question_formset = SurveyQuestionFormSet(instance=campaign) if campaign else None

    ingest_url = request.build_absolute_uri(reverse('survey-ingest'))
    return render(request, 'surveys/settings.html', {
        'flags_form': flags_form,
        'campaign_form': campaign_form,
        'question_formset': question_formset,
        'campaign': campaign if campaign and campaign.pk else None,
        'ingest_url': ingest_url,
    })


@login_required
def regenerate_token(request, pk):
    company = getattr(request.user, 'company', None)
    if not company or request.user.role not in ('company_admin', 'superadmin'):
        raise Http404
    campaign = get_object_or_404(SurveyCampaign, pk=pk, company=company)
    campaign.regenerate_token()
    messages.success(request, 'Ingest token regenerated. Update your CFD app with the new token.')
    return redirect('surveys:settings')
