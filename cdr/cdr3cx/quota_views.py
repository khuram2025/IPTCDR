from decimal import Decimal
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Quota, UserQuota, Extension
from .forms import QuotaForm, AssignQuotaForm
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .blockExternalCall import set_external_call
from accounts.views import is_company_admin


class CompanyAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_company_admin(self.request.user)
    
    def get_queryset(self):
        return self.model.objects.filter(company=self.request.user.company)


class QuotaListView(CompanyAdminMixin, ListView):
    model = Quota
    template_name = 'cdr/quota/quota_list.html'
    context_object_name = 'quotas'

class QuotaCreateView(CompanyAdminMixin, CreateView):
    model = Quota
    form_class = QuotaForm
    template_name = 'cdr/quota/quota_form.html'
    success_url = reverse_lazy('cdr3cx:quota_list')

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)

class QuotaUpdateView(CompanyAdminMixin, UpdateView):
    model = Quota
    form_class = QuotaForm
    template_name = 'cdr/quota/quota_form.html'
    success_url = reverse_lazy('cdr3cx:quota_list')

class QuotaDeleteView(CompanyAdminMixin, DeleteView):
    model = Quota
    template_name = 'cdr/quota/quota_confirm_delete.html'
    success_url = reverse_lazy('cdr3cx:quota_list')

@login_required
@user_passes_test(is_company_admin)
def assign_quota(request):
    print(f"User: {request.user}, Company: {request.user.company}")
    print(f"Number of extensions for company: {Extension.objects.filter(company=request.user.company).count()}")
    
    if request.method == 'POST':
        form = AssignQuotaForm(request.POST, company=request.user.company)
        if form.is_valid():
            quota = form.cleaned_data['quota']
            extensions = form.cleaned_data['extensions']
            print(f"Form is valid. Quota: {quota}, Extensions: {extensions}")
            for extension in extensions:
                user_quota, created = UserQuota.objects.get_or_create(extension=extension)
                user_quota.quota = quota
                user_quota.reset_quota()
                user_quota.save()
            messages.success(request, f"Quota successfully assigned to {len(extensions)} extension(s).")
            return redirect('cdr3cx:quota_list')
        else:
            print(f"Form errors: {form.errors}")
            messages.error(request, "There was an error assigning the quota. Please check the form and try again.")
    else:
        form = AssignQuotaForm(company=request.user.company)
    
    context = {
        'form': form,
        'extension_count': Extension.objects.filter(company=request.user.company).count()
    }
    return render(request, 'cdr/quota/assign_quota.html', context)

from django.core.paginator import Paginator
from django.db.models import F, Q, Value, ExpressionWrapper, DecimalField

@require_POST
@login_required
@user_passes_test(is_company_admin)
def toggle_external_call(request):
    extension_id = request.POST.get('extension_id')
    action = request.POST.get('action')  # 'block' or 'allow'
    try:
        extension = Extension.objects.select_related('company').get(pk=extension_id)
        # Tenant isolation: a company admin may only toggle their own extensions.
        if extension.company_id != request.user.company_id:
            return JsonResponse({'success': False, 'error': 'Not allowed for this extension'})

        company = extension.company
        if not (company and company.pbx_api_url and company.pbx_api_user
                and company.pbx_api_password):
            return JsonResponse({
                'success': False,
                'error': 'No 3CX API credentials configured for this company.'})

        allow_external = action == 'allow'
        # Use the OWNING company's PBX creds (never a hardcoded PBX).
        pbx_success = set_external_call(
            extension.extension, allow_external,
            base_url=company.pbx_api_url,
            user=company.pbx_api_user,
            password=company.pbx_api_password,
        )
        if pbx_success:
            extension.disable_external_call = not allow_external
            extension.save()
            return JsonResponse({'success': True, 'new_status': not allow_external})
        else:
            return JsonResponse({'success': False, 'error': 'PBX API call failed'})
    except Extension.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Extension not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def _quota_usage_base_qs(company):
    """User quotas for one company with remaining balance annotated."""
    return UserQuota.objects.select_related('extension', 'quota').filter(
        extension__company=company
    ).annotate(
        calculated_remaining_balance=ExpressionWrapper(
            F('total_amount') - F('used_amount'),
            output_field=DecimalField(),
        )
    )


@login_required
@user_passes_test(is_company_admin)
def quota_usage(request):
    company = request.user.company
    user_quotas = _quota_usage_base_qs(company)

    search_query = (request.GET.get('search') or '').strip()
    if search_query:
        user_quotas = user_quotas.filter(
            Q(extension__extension__icontains=search_query)
            | Q(extension__full_name__icontains=search_query)
            | Q(extension__display_name__icontains=search_query)
            | Q(extension__email__icontains=search_query)
        )

    quota_filter = request.GET.get('quota', '')
    if quota_filter:
        user_quotas = user_quotas.filter(quota_id=quota_filter)

    balance_status = request.GET.get('balance', '')
    low_threshold = Value(Decimal('0.25'))
    if balance_status == 'exhausted':
        user_quotas = user_quotas.filter(calculated_remaining_balance__lte=0)
    elif balance_status == 'low':
        user_quotas = user_quotas.filter(
            calculated_remaining_balance__gt=0,
            calculated_remaining_balance__lte=F('total_amount') * low_threshold,
        )
    elif balance_status == 'healthy':
        user_quotas = user_quotas.filter(
            calculated_remaining_balance__gt=F('total_amount') * low_threshold,
        )

    blocked = request.GET.get('blocked', '')
    if blocked in ('0', '1'):
        user_quotas = user_quotas.filter(
            extension__disable_external_call=(blocked == '1')
        )

    base_qs = _quota_usage_base_qs(company)
    stats = {
        'total': base_qs.count(),
        'exhausted': base_qs.filter(calculated_remaining_balance__lte=0).count(),
        'low': base_qs.filter(
            calculated_remaining_balance__gt=0,
            calculated_remaining_balance__lte=F('total_amount') * low_threshold,
        ).count(),
        'blocked': base_qs.filter(extension__disable_external_call=True).count(),
    }

    sort_by = request.GET.get('sort', 'extension__extension')
    if sort_by == 'used_amount':
        user_quotas = user_quotas.order_by('used_amount')
    elif sort_by == '-used_amount':
        user_quotas = user_quotas.order_by('-used_amount')
    elif sort_by == 'remaining_balance':
        user_quotas = user_quotas.order_by('calculated_remaining_balance')
    elif sort_by == '-remaining_balance':
        user_quotas = user_quotas.order_by('-calculated_remaining_balance')
    elif sort_by.startswith('-'):
        user_quotas = user_quotas.order_by(F(sort_by[1:]).desc(nulls_last=True))
    else:
        user_quotas = user_quotas.order_by(F(sort_by).asc(nulls_last=True))

    paginator = Paginator(user_quotas, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)

    return render(request, 'cdr/quota/quota_usage.html', {
        'page_obj': page_obj,
        'sort_by': sort_by,
        'search_query': search_query,
        'quota_filter': quota_filter,
        'balance_status': balance_status,
        'blocked': blocked,
        'quota_plans': Quota.objects.filter(company=company).order_by('name'),
        'stats': stats,
        'result_count': paginator.count,
        'querystring': params.urlencode(),
    })

from django.template.loader import render_to_string
from django.shortcuts import render, get_object_or_404, redirect
from django.core.mail import send_mail
from django.conf import settings
from .notification_utils import resolve_extension_alert_email


# cdr3cx/views.py

from decimal import Decimal

@login_required
@user_passes_test(is_company_admin)
def send_quota_email(request, extension_id):
    extension = get_object_or_404(Extension, pk=extension_id)

    if not extension.email:
        messages.error(request, 'No email associated with this extension.')
        return redirect('cdr3cx:quota_usage')

    try:
        user_quota = UserQuota.objects.get(extension=extension)
    except UserQuota.DoesNotExist:
        messages.error(request, 'No quota information found for this extension.')
        return redirect('cdr3cx:quota_usage')

    full_name = extension.full_name or f"{extension.first_name or ''} {extension.last_name or ''}".strip() or 'User'

    # Calculate used_amount
    total_amount = user_quota.quota.amount if user_quota.quota else Decimal('0.00')
    remaining_balance = user_quota.remaining_balance
    used_amount = total_amount - remaining_balance

    subject = 'Your Quota Usage Status'
    message = render_to_string('cdr/quota/quota_status_email.html', {
        'full_name': full_name,
        'extension_number': extension.extension,
        'quota_name': user_quota.quota.name if user_quota.quota else 'N/A',
        'total_amount': total_amount,
        'used_amount': used_amount,
        'remaining_balance': remaining_balance,
    })

    recipient_email = resolve_extension_alert_email(extension)

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
            fail_silently=False,
        )
        messages.success(request, f'Email sent successfully to {recipient_email}.')
    except Exception as e:
        messages.error(request, f'Error sending email: {str(e)}')

    return redirect('cdr3cx:quota_usage')


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import UserQuota, Extension
from decimal import Decimal, InvalidOperation

@login_required
@user_passes_test(is_company_admin)
def add_balance(request, extension_id):
    extension = get_object_or_404(Extension, id=extension_id)
    user_quota = get_object_or_404(UserQuota, extension=extension)

    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', '0'))
            if amount <= 0:
                raise ValueError("Amount must be positive")
            
            success = user_quota.add_custom_balance(amount)
            if success:
                messages.success(request, f"Successfully added {amount} to the balance.")
            else:
                messages.error(request, "Failed to add balance.")
        except (InvalidOperation, ValueError) as e:
            messages.error(request, f"Invalid amount: {str(e)}")
        
        return redirect('cdr3cx:add_balance', extension_id=extension_id)

    context = {
        'extension': extension,
        'user_quota': user_quota,
    }
    return render(request, 'cdr/quota/add_balance.html', context)