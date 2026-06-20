import json

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from accounts.views import is_company_admin
from .callpattern_presets import (
    COUNTRY_CATALOG,
    PATTERN_MODES,
    QUICK_RATE_CHIPS,
    RULE_PRESETS,
    TEST_NUMBERS_DEFAULT,
    country_catalog_enriched,
    get_country_by_dial,
    get_country_by_iso,
    regex_from_stored,
)
from .forms import CallPatternForm
from .models import CallPattern
import re


class CompanyAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_company_admin(self.request.user)

    def get_queryset(self):
        return CallPattern.objects.filter(company=self.request.user.company)


def _wizard_context(default_mode='country'):
    catalog = country_catalog_enriched()
    return {
        'pattern_modes_json': json.dumps(PATTERN_MODES),
        'rule_presets_json': json.dumps(RULE_PRESETS),
        'country_catalog_json': json.dumps(catalog),
        'rate_chips_json': json.dumps(QUICK_RATE_CHIPS),
        'test_numbers_json': json.dumps(TEST_NUMBERS_DEFAULT),
        'pattern_modes': PATTERN_MODES,
        'rule_presets': RULE_PRESETS,
        'country_presets': COUNTRY_CATALOG,
        'country_catalog': catalog,
        'rate_chips': QUICK_RATE_CHIPS,
        'test_numbers': TEST_NUMBERS_DEFAULT,
        'default_wizard_mode': default_mode,
    }


class CallPatternListView(CompanyAdminMixin, ListView):
    model = CallPattern
    template_name = 'cdr/callpatterns/list.html'
    context_object_name = 'callpatterns'
    paginate_by = 25

    def get_queryset(self):
        return super().get_queryset().order_by('call_type', 'name')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        patterns = list(CallPattern.objects.filter(company=self.request.user.company))
        ctx['type_counts'] = {
            t: sum(1 for p in patterns if p.call_type == t)
            for t, _ in CallPattern.CALL_TYPE_CHOICES
        }
        ctx['avg_rate'] = (
            sum(p.rate_per_min for p in patterns) / len(patterns) if patterns else 0
        )
        ctx['total_rules'] = len(patterns)
        return ctx


class CallPatternFormMixin:
    template_name = 'cdr/callpatterns/form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        default_mode = 'prefix' if getattr(self, 'object', None) and self.object.pk else 'country'
        ctx.update(_wizard_context(default_mode=default_mode))
        obj = getattr(self, 'object', None)
        ctx['is_edit'] = bool(obj and obj.pk)
        ctx['action'] = 'Update' if ctx['is_edit'] else 'Create'
        if obj and obj.pk:
            ctx['stored_regex'] = obj.get_regex_pattern()
        return ctx


class CallPatternCreateView(CompanyAdminMixin, CallPatternFormMixin, CreateView):
    model = CallPattern
    form_class = CallPatternForm
    success_url = reverse_lazy('cdr3cx:callpattern-list')

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        messages.success(self.request, 'Calling rule created successfully.')
        return super().form_valid(form)


class CallPatternUpdateView(CompanyAdminMixin, CallPatternFormMixin, UpdateView):
    model = CallPattern
    form_class = CallPatternForm
    success_url = reverse_lazy('cdr3cx:callpattern-list')

    def form_valid(self, form):
        messages.success(self.request, 'Calling rule updated successfully.')
        return super().form_valid(form)


class CallPatternDeleteView(CompanyAdminMixin, DeleteView):
    model = CallPattern
    template_name = 'cdr/callpatterns/confirm_delete.html'
    success_url = reverse_lazy('cdr3cx:callpattern-list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Calling rule deleted successfully.')
        return super().delete(request, *args, **kwargs)


@login_required
@user_passes_test(is_company_admin)
@require_POST
def callpattern_test_pattern(request):
    """AJAX: test numbers against a pattern string (live preview in the wizard)."""
    import json as _json
    try:
        body = _json.loads(request.body.decode() or '{}')
    except _json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    pattern = (body.get('pattern') or '').strip()
    numbers = body.get('numbers') or []
    if not pattern:
        return JsonResponse({'error': 'Pattern required'}, status=400)

    try:
        regex = re.compile(regex_from_stored(pattern))
    except re.error as exc:
        return JsonResponse({'error': str(exc), 'regex': ''}, status=400)

    results = []
    for raw in numbers:
        num = str(raw).strip()
        if not num:
            continue
        results.append({'number': num, 'match': bool(regex.match(num))})

    return JsonResponse({
        'regex': regex_from_stored(pattern),
        'results': results,
        'match_count': sum(1 for r in results if r['match']),
    })


@login_required
@user_passes_test(is_company_admin)
def callpattern_country_meta(request):
    """Return smart pattern + formats for a selected country."""
    iso = request.GET.get('iso', '').strip()
    dial = request.GET.get('dial', '').strip()
    meta = get_country_by_iso(iso) if iso else get_country_by_dial(dial)
    if not meta:
        return JsonResponse({'error': 'Country not found'}, status=404)
    return JsonResponse(meta)


@login_required
@user_passes_test(is_company_admin)
@require_POST
def callpattern_bulk_create(request):
    """Create one calling rule per selected country (bulk add rates)."""
    try:
        body = json.loads(request.body.decode() or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    isos = body.get('countries') or []
    if not isinstance(isos, list) or not isos:
        return JsonResponse({'error': 'Select at least one country'}, status=400)

    use_hints = body.get('use_rate_hints', True)
    default_rate = body.get('rate')
    rate_override = None
    if default_rate is not None and str(default_rate).strip() != '':
        try:
            rate_override = Decimal(str(default_rate))
        except (InvalidOperation, ValueError):
            return JsonResponse({'error': 'Invalid rate'}, status=400)

    company = request.user.company
    existing_patterns = set(
        CallPattern.objects.filter(company=company).values_list('pattern', flat=True)
    )
    existing_names = set(
        CallPattern.objects.filter(company=company).values_list('name', flat=True)
    )

    created = []
    skipped = []

    for raw_iso in isos:
        iso = str(raw_iso).strip().upper()
        meta = get_country_by_iso(iso)
        if not meta:
            skipped.append({'iso': iso, 'reason': 'not_found'})
            continue

        pattern = meta['pattern']
        name = meta['rule_name']
        if pattern in existing_patterns or name in existing_names:
            skipped.append({'iso': iso, 'name': name, 'reason': 'duplicate'})
            continue

        if rate_override is not None:
            rate = rate_override
        elif use_hints:
            rate = Decimal(str(meta.get('rate_hint', 1.00)))
        else:
            rate = Decimal('1.00')

        CallPattern.objects.create(
            company=company,
            name=name,
            pattern=pattern,
            call_type='international',
            rate_per_min=rate,
            description=meta['name'],
        )
        existing_patterns.add(pattern)
        existing_names.add(name)
        created.append({'iso': iso, 'name': name, 'rate': float(rate)})

    if created and not skipped:
        messages.success(
            request,
            f'Created {len(created)} international calling rule(s).',
        )
    elif created:
        messages.warning(
            request,
            f'Created {len(created)} rule(s); skipped {len(skipped)} duplicate(s).',
        )
    elif skipped:
        messages.info(request, 'No new rules created — selected countries already exist.')

    return JsonResponse({
        'created': created,
        'skipped': skipped,
        'created_count': len(created),
        'skipped_count': len(skipped),
        'redirect': reverse('cdr3cx:callpattern-list'),
    })
