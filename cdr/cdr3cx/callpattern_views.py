from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from .models import CallPattern
from .forms import CallPatternForm
from accounts.views import is_company_admin


class CompanyAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_company_admin(self.request.user)
    
    def get_queryset(self):
        return CallPattern.objects.filter(company=self.request.user.company)


class CallPatternListView(CompanyAdminMixin, ListView):
    model = CallPattern
    template_name = 'cdr/callpatterns/list.html'
    context_object_name = 'callpatterns'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.order_by('-id')


class CallPatternCreateView(CompanyAdminMixin, CreateView):
    model = CallPattern
    form_class = CallPatternForm
    template_name = 'cdr/callpatterns/form.html'
    success_url = reverse_lazy('cdr3cx:callpattern-list')
    
    def form_valid(self, form):
        form.instance.company = self.request.user.company
        messages.success(self.request, 'Call pattern created successfully.')
        return super().form_valid(form)


class CallPatternUpdateView(CompanyAdminMixin, UpdateView):
    model = CallPattern
    form_class = CallPatternForm
    template_name = 'cdr/callpatterns/form.html'
    success_url = reverse_lazy('cdr3cx:callpattern-list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Call pattern updated successfully.')
        return super().form_valid(form)


class CallPatternDeleteView(CompanyAdminMixin, DeleteView):
    model = CallPattern
    template_name = 'cdr/callpatterns/confirm_delete.html'
    success_url = reverse_lazy('cdr3cx:callpattern-list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Call pattern deleted successfully.')
        return super().delete(request, *args, **kwargs)


@login_required
@user_passes_test(is_company_admin)
def callpattern_list(request):
    callpatterns = CallPattern.objects.filter(company=request.user.company).order_by('-id')
    return render(request, 'cdr/callpatterns/list.html', {'callpatterns': callpatterns})


@login_required
@user_passes_test(is_company_admin)
def callpattern_create(request):
    if request.method == 'POST':
        form = CallPatternForm(request.POST)
        if form.is_valid():
            callpattern = form.save(commit=False)
            callpattern.company = request.user.company
            callpattern.save()
            messages.success(request, 'Call pattern created successfully.')
            return redirect('cdr3cx:callpattern-list')
    else:
        form = CallPatternForm()
    
    return render(request, 'cdr/callpatterns/form.html', {
        'form': form,
        'action': 'Create'
    })


@login_required
@user_passes_test(is_company_admin)
def callpattern_edit(request, pk):
    callpattern = get_object_or_404(CallPattern, pk=pk, company=request.user.company)
    
    if request.method == 'POST':
        form = CallPatternForm(request.POST, instance=callpattern)
        if form.is_valid():
            form.save()
            messages.success(request, 'Call pattern updated successfully.')
            return redirect('cdr3cx:callpattern-list')
    else:
        form = CallPatternForm(instance=callpattern)
    
    return render(request, 'cdr/callpatterns/form.html', {
        'form': form,
        'action': 'Update',
        'callpattern': callpattern
    })


@login_required
@user_passes_test(is_company_admin)
def callpattern_delete(request, pk):
    callpattern = get_object_or_404(CallPattern, pk=pk, company=request.user.company)
    
    if request.method == 'POST':
        callpattern.delete()
        messages.success(request, 'Call pattern deleted successfully.')
        return redirect('callpattern-list')
    
    return render(request, 'cdr/callpatterns/confirm_delete.html', {
        'callpattern': callpattern
    })