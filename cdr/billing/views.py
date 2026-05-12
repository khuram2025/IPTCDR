"""HTML views for the billing/fraud dashboard."""
import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import FraudIncident, FraudRule
from .services.audit_report import analyze, parse_cdr_csv, render_pdf


@login_required
def fraud_incident_dashboard(request):
    """List of fraud incidents for the current company.

    Filters: ?status=open|acknowledged|resolved|false_positive|active|all
             ?severity=low|medium|high|critical
    Default view shows open + acknowledged.
    """
    company = getattr(request.user, 'company', None)
    if company is None:
        return render(request, 'billing/fraud_incident_dashboard.html',
                      {'incidents': [], 'stats': {}, 'company': None})

    qs = FraudIncident.objects.filter(company=company).select_related('rule', 'triggering_call')

    status_filter = request.GET.get('status', 'active')
    if status_filter == 'active':
        qs = qs.filter(status__in=['open', 'acknowledged'])
    elif status_filter != 'all':
        qs = qs.filter(status=status_filter)

    severity_filter = request.GET.get('severity')
    if severity_filter:
        qs = qs.filter(severity=severity_filter)

    qs = qs.order_by('-detected_at')

    stats = {
        'open':     FraudIncident.objects.filter(company=company, status='open').count(),
        'critical': FraudIncident.objects.filter(company=company, severity='critical',
                                                 status__in=['open', 'acknowledged']).count(),
        'high':     FraudIncident.objects.filter(company=company, severity='high',
                                                 status__in=['open', 'acknowledged']).count(),
        'last_24h': FraudIncident.objects.filter(
            company=company, detected_at__gte=timezone.now() - timezone.timedelta(hours=24),
        ).count(),
    }
    rule_count = FraudRule.objects.filter(company=company, is_active=True).count()
    rules_in_shadow = FraudRule.objects.filter(
        company=company, is_active=True, shadow_mode=True,
    ).count()

    return render(request, 'billing/fraud_incident_dashboard.html', {
        'incidents': qs[:200],
        'stats': stats,
        'rule_count': rule_count,
        'rules_in_shadow': rules_in_shadow,
        'company': company,
        'status_filter': status_filter,
        'severity_filter': severity_filter,
    })


@login_required
def acknowledge_incident(request, incident_id):
    company = getattr(request.user, 'company', None)
    incident = get_object_or_404(FraudIncident, pk=incident_id, company=company)
    if request.method == 'POST':
        incident.status = 'acknowledged'
        incident.save(update_fields=['status'])
        messages.success(request, f"Incident #{incident.pk} acknowledged.")
    return redirect('billing:fraud_incidents')


@login_required
def resolve_incident(request, incident_id):
    company = getattr(request.user, 'company', None)
    incident = get_object_or_404(FraudIncident, pk=incident_id, company=company)
    if request.method == 'POST':
        incident.status = 'resolved'
        incident.resolved_at = timezone.now()
        incident.resolved_by = request.user
        incident.save(update_fields=['status', 'resolved_at', 'resolved_by'])
        messages.success(request, f"Incident #{incident.pk} resolved.")
    return redirect('billing:fraud_incidents')


@login_required
def mark_false_positive(request, incident_id):
    company = getattr(request.user, 'company', None)
    incident = get_object_or_404(FraudIncident, pk=incident_id, company=company)
    if request.method == 'POST':
        incident.status = 'false_positive'
        incident.resolved_at = timezone.now()
        incident.resolved_by = request.user
        incident.save(update_fields=['status', 'resolved_at', 'resolved_by'])
        messages.info(request, f"Incident #{incident.pk} marked as false positive.")
    return redirect('billing:fraud_incidents')


# ---------------------------------------------------------------------------
# Free toll-fraud audit (lead-gen) — public, no login required
# ---------------------------------------------------------------------------


MAX_AUDIT_SIZE = 5 * 1024 * 1024  # 5 MB


@require_http_methods(['GET', 'POST'])
def free_fraud_audit(request):
    """Public landing page → CSV upload → branded PDF audit report.

    Stores no CDR data — file is parsed in-memory and discarded after the
    PDF response is built.
    """
    error = None
    if request.method == 'POST':
        upload = request.FILES.get('cdr_csv')
        contact_name = request.POST.get('contact_name', '').strip()[:128]
        contact_company = request.POST.get('contact_company', '').strip()[:128]
        contact_email = request.POST.get('contact_email', '').strip()[:128]
        if not upload:
            error = "Please attach a CSV file."
        elif upload.size > MAX_AUDIT_SIZE:
            error = "File too large (5 MB max)."
        else:
            try:
                rows = parse_cdr_csv(upload)
            except Exception as exc:
                rows = []
                error = f"Could not parse CSV: {exc}"
            if not error and not rows:
                error = "No usable rows found. Required columns: callee (call_time, caller, duration, total_cost recommended)."
            if not error:
                report = analyze(rows)
                pdf = render_pdf(report,
                                 contact_name=contact_name,
                                 contact_company=contact_company,
                                 brand='IPT Portal')
                # TODO: enqueue lead capture (CRM webhook) using contact_*
                resp = HttpResponse(pdf, content_type='application/pdf')
                resp['Content-Disposition'] = 'attachment; filename="iptportal-fraud-audit.pdf"'
                return resp

    return render(request, 'billing/free_fraud_audit.html', {'error': error})
