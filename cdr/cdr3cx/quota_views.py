from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from .models import Quota, UserQuota, Extension
from .forms import QuotaForm, AssignQuotaForm
from django.contrib import messages

class QuotaListView(LoginRequiredMixin, ListView):
    model = Quota
    template_name = 'cdr/quota/quota_list.html'
    context_object_name = 'quotas'

    def get_queryset(self):
        return Quota.objects.filter(company=self.request.user.company)

class QuotaCreateView(LoginRequiredMixin, CreateView):
    model = Quota
    form_class = QuotaForm
    template_name = 'cdr/quota/quota_form.html'
    success_url = reverse_lazy('cdr3cx:quota_list')

    def form_valid(self, form):
        form.instance.company = self.request.user.company
        return super().form_valid(form)

class QuotaUpdateView(LoginRequiredMixin, UpdateView):
    model = Quota
    form_class = QuotaForm
    template_name = 'cdr/quota/quota_form.html'
    success_url = reverse_lazy('cdr3cx:quota_list')

class QuotaDeleteView(LoginRequiredMixin, DeleteView):
    model = Quota
    template_name = 'cdr/quota/quota_confirm_delete.html'
    success_url = reverse_lazy('cdr3cx:quota_list')

@login_required
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
from django.db.models import F

from django.db.models import F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce

@login_required
def quota_usage(request):
    user_quotas = UserQuota.objects.filter(extension__company=request.user.company).select_related('extension', 'quota')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        user_quotas = user_quotas.filter(extension__extension__icontains=search_query)
    
    # Add Used Amount as an annotation
    user_quotas = user_quotas.annotate(
        used_amount=ExpressionWrapper(
            Coalesce(F('quota__amount'), 0) - F('remaining_balance'),
            output_field=DecimalField()
        )
    )
    
    # Sorting
    sort_by = request.GET.get('sort', 'extension__extension')
    if sort_by == 'used_amount':
        user_quotas = user_quotas.order_by('used_amount')
    elif sort_by == '-used_amount':
        user_quotas = user_quotas.order_by('-used_amount')
    elif sort_by.startswith('-'):
        user_quotas = user_quotas.order_by(F(sort_by[1:]).desc(nulls_last=True))
    else:
        user_quotas = user_quotas.order_by(F(sort_by).asc(nulls_last=True))
    
    # Pagination
    paginator = Paginator(user_quotas, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'cdr/quota/quota_usage.html', {
        'page_obj': page_obj, 
        'sort_by': sort_by,
        'search_query': search_query
    })