"""HTML views for the security/audit dashboard."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import AuditLogEntry


@login_required
def audit_log(request):
    """Browsable audit log scoped to the user's company.

    Filters: ?user=email&method=POST&q=path-substring
    """
    company = getattr(request.user, 'company', None)
    qs = AuditLogEntry.objects.filter(company=company) if company else AuditLogEntry.objects.none()

    user_email = request.GET.get('user', '').strip()
    if user_email:
        qs = qs.filter(user_email__icontains=user_email)

    method = request.GET.get('method', '').strip()
    if method:
        qs = qs.filter(method=method.upper())

    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(path__icontains=q)

    status = request.GET.get('status', '').strip()
    if status:
        qs = qs.filter(status_code=status)

    qs = qs.select_related('user').order_by('-created_at')[:500]

    return render(request, 'security/audit_log.html', {
        'entries': qs,
        'filters': {'user': user_email, 'method': method, 'q': q, 'status': status},
    })
