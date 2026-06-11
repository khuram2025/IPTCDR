"""Extension directory — list + detail UIs over the 3CX-synced accounts.Extension.

Extensions are kept in sync one-way from each tenant's 3CX by
``acd.tasks.sync_3cx_users`` (every 6h + a manual "Sync now" button here). These
views are read-only over that data, plus a thin POST to trigger an on-demand sync.
Access is role-based (see ``can_view_extensions``); quota/PBX mutations stay
company-admin only and reuse the existing quota endpoints.
"""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Avg, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Extension
from accounts.views import is_company_admin
from .models import CallRecord


def can_view_extensions(user):
    """Role-based gate: superadmin/company_admin always; otherwise only if the
    user was granted the ``accounts.view_extension`` permission through a custom
    Role (UserRole -> Role.permissions) or directly via user/group permissions.
    """
    if not user.is_authenticated:
        return False
    if getattr(user, 'role', None) in ('superadmin', 'company_admin'):
        return True
    if user.has_perm('accounts.view_extension'):
        return True
    from accounts.models import UserRole
    return UserRole.objects.filter(
        user=user,
        role__is_active=True,
        role__permissions__codename='view_extension',
        role__permissions__content_type__app_label='accounts',
    ).exists()


def _scoped_extensions(user):
    """Extensions visible to this user: their company's (all, for superadmin)."""
    qs = Extension.objects.select_related('company', 'quota', 'quota__quota')
    if getattr(user, 'role', None) == 'superadmin':
        return qs
    return qs.filter(company=user.company)


@login_required
@user_passes_test(can_view_extensions)
def extension_list(request):
    qs = _scoped_extensions(request.user)

    # --- filters ---
    search = (request.GET.get('q') or '').strip()
    if search:
        qs = qs.filter(
            Q(extension__icontains=search)
            | Q(full_name__icontains=search)
            | Q(display_name__icontains=search)
            | Q(email__icontains=search)
            | Q(mobile__icontains=search)
        )

    show = request.GET.get('show', 'active')  # active | inactive | all
    if show == 'active':
        qs = qs.filter(is_active=True)
    elif show == 'inactive':
        qs = qs.filter(is_active=False)

    registered = request.GET.get('registered')  # '1' | '0' | None
    if registered in ('0', '1'):
        qs = qs.filter(is_registered=(registered == '1'))

    blocked = request.GET.get('blocked')  # external-call blocked
    if blocked in ('0', '1'):
        qs = qs.filter(disable_external_call=(blocked == '1'))

    has_quota = request.GET.get('quota')
    if has_quota == '1':
        qs = qs.filter(quota__quota__isnull=False)
    elif has_quota == '0':
        qs = qs.filter(quota__quota__isnull=True)

    qs = qs.order_by('extension')

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    scope = _scoped_extensions(request.user)
    last_synced = scope.order_by('-last_synced_at').values_list(
        'last_synced_at', flat=True).first()

    # Preserve current filters across pagination links.
    params = request.GET.copy()
    params.pop('page', None)

    context = {
        'page_obj': page_obj,
        'total': scope.count(),
        'active_count': scope.filter(is_active=True).count(),
        'result_count': paginator.count,
        'search': search,
        'show': show,
        'registered': registered or '',
        'blocked': blocked or '',
        'has_quota': has_quota or '',
        'last_synced': last_synced,
        'is_admin': is_company_admin(request.user),
        'querystring': params.urlencode(),
    }
    return render(request, 'cdr/extensions/extension_list.html', context)


@login_required
@user_passes_test(can_view_extensions)
def extension_detail(request, pk):
    ext = get_object_or_404(_scoped_extensions(request.user), pk=pk)
    number = ext.extension

    # Compact recent activity (last 90 days) — calls this extension made
    # (caller = from-dn) or answered (final_dn). The full call-center page has the
    # deep ACD view; we link to it rather than duplicate it.
    since = timezone.now() - timedelta(days=90)
    calls = CallRecord.objects.filter(
        company=ext.company, call_time__gte=since
    ).filter(Q(final_dn=number) | Q(caller=number))

    total_calls = calls.count()
    answered_calls = calls.filter(time_answered__isnull=False).count()
    avg_duration = calls.aggregate(a=Avg('duration'))['a'] or 0
    answer_rate = round(answered_calls / total_calls * 100, 1) if total_calls else 0
    recent_calls = list(calls.order_by('-call_time')[:25])

    context = {
        'ext': ext,
        'user_quota': getattr(ext, 'quota', None),
        'total_calls': total_calls,
        'answered_calls': answered_calls,
        'answer_rate': answer_rate,
        'avg_duration': int(avg_duration),
        'recent_calls': recent_calls,
        'activity_days': 90,
        'is_admin': is_company_admin(request.user),
    }
    return render(request, 'cdr/extensions/extension_detail.html', context)


@require_POST
@login_required
@user_passes_test(is_company_admin)
def sync_extensions_now(request):
    """Queue an on-demand 3CX extension sync for the admin's company."""
    from acd.tasks import sync_3cx_users

    company = request.user.company
    if not company:
        messages.error(request, 'No company is associated with your account.')
        return redirect('cdr3cx:extension_list')
    if not (company.pbx_api_url and company.pbx_api_user and company.pbx_api_password):
        messages.error(request, 'This company has no 3CX API credentials configured.')
        return redirect('cdr3cx:extension_list')
    try:
        sync_3cx_users.delay(company_id=company.id)
        messages.success(
            request, 'Extension sync started from 3CX — refresh in a moment to see updates.')
    except Exception as e:
        messages.error(request, f'Could not start sync: {e}')
    return redirect('cdr3cx:extension_list')
