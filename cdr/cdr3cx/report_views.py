"""Scheduled-report management UI (P3.1): list / create / edit / run-now /
download, plus an ad-hoc generate-and-download. All views are company-scoped.
"""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from acd.models import ScheduledReport, ReportRun
from acd.reports import (
    REPORT_TYPES, REPORT_DESCRIPTIONS, WINDOWS, build_report, render_report, resolve_window,
)


@login_required
def reports_hub(request):
    """Modern unified Reports hub: every Call Control + Call Center report grouped
    into cards with a shared date range and one-click Excel / PDF / CSV / View."""
    from acd.reports import report_groups
    return render(request, 'cdr/reports/hub.html', {
        'groups': report_groups(),
        'generate_url': reverse('cdr3cx:report_generate_now'),
    })


@login_required
def report_catalog(request):
    """Browsable catalog of every available report with a one-line description and
    quick run / schedule actions (P3.2)."""
    catalog = [{'key': k, 'label': v[0], 'description': REPORT_DESCRIPTIONS.get(k, '')}
               for k, v in REPORT_TYPES.items()]
    return render(request, 'cdr/reports/catalog.html', {
        'catalog': catalog, 'windows': WINDOWS, 'formats': ['csv', 'xlsx', 'pdf', 'html'],
    })


class ScheduledReportForm(forms.ModelForm):
    class Meta:
        model = ScheduledReport
        fields = ['name', 'report_type', 'window', 'fmt', 'recurrence',
                  'hour', 'minute', 'weekday', 'day_of_month', 'recipients', 'is_active']
        widgets = {
            'recipients': forms.Textarea(attrs={'rows': 2,
                'placeholder': 'ops@example.com, supervisor@example.com'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = 'form-check-input' if name == 'is_active' else 'form-select' \
                if isinstance(field.widget, forms.Select) else 'form-control'
            field.widget.attrs.setdefault('class', css)


@login_required
def report_list(request):
    if not request.user.company:
        return render(request, 'cdr/reports/list.html', {'error': 'No company assigned'})
    company = request.user.company
    reports = ScheduledReport.objects.filter(company=company)
    runs = (ReportRun.objects.filter(company=company)
            .select_related('scheduled_report')[:25])
    return render(request, 'cdr/reports/list.html', {
        'reports': reports, 'runs': runs,
        'report_types': REPORT_TYPES, 'windows': WINDOWS,
        'formats': ['csv', 'xlsx', 'pdf', 'html'],
    })


@login_required
def report_create(request):
    if not request.user.company:
        raise Http404
    form = ScheduledReportForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        sr = form.save(commit=False)
        sr.company = request.user.company
        sr.created_by = request.user
        sr.next_run_at = sr.compute_next_run()
        sr.save()
        messages.success(request, f'Scheduled report "{sr.name}" created.')
        return redirect('cdr3cx:report_list')
    return render(request, 'cdr/reports/form.html', {'form': form, 'mode': 'Create'})


@login_required
def report_edit(request, pk):
    sr = get_object_or_404(ScheduledReport, pk=pk, company=request.user.company)
    form = ScheduledReportForm(request.POST or None, instance=sr)
    if request.method == 'POST' and form.is_valid():
        sr = form.save(commit=False)
        sr.next_run_at = sr.compute_next_run()
        sr.save()
        messages.success(request, f'Scheduled report "{sr.name}" updated.')
        return redirect('cdr3cx:report_list')
    return render(request, 'cdr/reports/form.html',
                  {'form': form, 'mode': 'Edit', 'report': sr})


@login_required
def report_delete(request, pk):
    sr = get_object_or_404(ScheduledReport, pk=pk, company=request.user.company)
    if request.method == 'POST':
        name = sr.name
        sr.delete()
        messages.success(request, f'Deleted "{name}".')
    return redirect('cdr3cx:report_list')


@login_required
def report_run_now(request, pk):
    sr = get_object_or_404(ScheduledReport, pk=pk, company=request.user.company)
    if request.method == 'POST':
        from acd.tasks import run_scheduled_report
        try:
            run_scheduled_report.delay(sr.id)
            messages.success(request, f'"{sr.name}" queued — it will appear in Recent runs shortly.')
        except Exception:
            run_scheduled_report(sr.id)  # broker down: run inline
            messages.success(request, f'"{sr.name}" generated.')
    return redirect('cdr3cx:report_list')


@login_required
def report_download(request, pk):
    run = get_object_or_404(ReportRun, pk=pk, company=request.user.company)
    if run.status != 'success' or not run.file_path:
        raise Http404('Report file not available')
    try:
        with open(run.file_path, 'rb') as fh:
            content = fh.read()
    except OSError:
        raise Http404('Report file missing on disk')
    from acd.reports import _MIME
    resp = HttpResponse(content, content_type=_MIME.get(run.fmt, 'application/octet-stream'))
    resp['Content-Disposition'] = f'attachment; filename="{run.filename}"'
    return resp


@login_required
def report_generate_now(request):
    """Ad-hoc: build + stream a report immediately (no scheduling)."""
    if not request.user.company:
        raise Http404
    rtype = request.GET.get('type')
    window = request.GET.get('window', 'yesterday')
    fmt = request.GET.get('format', 'xlsx')
    start_raw = (request.GET.get('start') or '').strip()
    end_raw = (request.GET.get('end') or '').strip()
    if rtype not in REPORT_TYPES or fmt not in ('csv', 'xlsx', 'pdf', 'html'):
        messages.error(request, 'Invalid report selection.')
        return redirect('cdr3cx:report_list')
    # An explicit date range (carried from a page's filter) wins over a named window.
    if start_raw and end_raw:
        from datetime import datetime
        try:
            start = datetime.strptime(start_raw, '%Y-%m-%d').date()
            end = datetime.strptime(end_raw, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid date range.')
            return redirect('cdr3cx:report_list')
        label = f'{start_raw}_{end_raw}'
    else:
        if window not in WINDOWS:
            messages.error(request, 'Invalid report selection.')
            return redirect('cdr3cx:report_list')
        start, end = resolve_window(window)
        label = window
    data = build_report(rtype, request.user.company, start, end)
    content, mime, ext = render_report(data, fmt)
    stamp = timezone.localtime().strftime('%Y%m%d-%H%M%S')
    disp = 'inline' if fmt == 'html' else 'attachment'
    resp = HttpResponse(content, content_type=mime)
    resp['Content-Disposition'] = f'{disp}; filename="{rtype}_{label}_{stamp}.{ext}"'
    return resp
