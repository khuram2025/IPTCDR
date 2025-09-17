from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib.auth.models import Permission
from .models import Role, UserRole
from .forms import RoleForm, UserRoleAssignmentForm
from .views import is_company_admin


class CompanyAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_company_admin(self.request.user)
    
    def get_queryset(self):
        return Role.objects.filter(company=self.request.user.company)


class RoleListView(CompanyAdminMixin, ListView):
    model = Role
    template_name = 'accounts/roles/list.html'
    context_object_name = 'roles'
    paginate_by = 20
    
    def get_queryset(self):
        return super().get_queryset().order_by('-created_at')


class RoleCreateView(CompanyAdminMixin, CreateView):
    model = Role
    form_class = RoleForm
    template_name = 'accounts/roles/form.html'
    success_url = reverse_lazy('accounts:role_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = self.request.user.company
        return kwargs
    
    def form_valid(self, form):
        form.instance.company = self.request.user.company
        messages.success(self.request, f'Role "{form.instance.name}" created successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'Create'
        context['permissions_by_category'] = self._get_permissions_by_category()
        return context
    
    def _get_permissions_by_category(self):
        """Organize permissions by category for better UX"""
        permissions = Permission.objects.filter(
            content_type__app_label__in=['accounts', 'cdr3cx']
        ).order_by('content_type__app_label', 'codename')
        
        categories = {
            'User Management': [],
            'Company Management': [],
            'Extension Management': [],
            'Call Records': [],
            'Call Patterns': [],
            'Quota Management': [],
            'Other': []
        }
        
        for perm in permissions:
            categorized = False
            if 'user' in perm.codename or 'customuser' in perm.codename:
                categories['User Management'].append(perm)
                categorized = True
            elif 'company' in perm.codename:
                categories['Company Management'].append(perm)
                categorized = True
            elif 'extension' in perm.codename:
                categories['Extension Management'].append(perm)
                categorized = True
            elif 'callrecord' in perm.codename:
                categories['Call Records'].append(perm)
                categorized = True
            elif 'callpattern' in perm.codename:
                categories['Call Patterns'].append(perm)
                categorized = True
            elif 'quota' in perm.codename or 'userquota' in perm.codename:
                categories['Quota Management'].append(perm)
                categorized = True
            
            if not categorized:
                categories['Other'].append(perm)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}


class RoleUpdateView(CompanyAdminMixin, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = 'accounts/roles/form.html'
    success_url = reverse_lazy('accounts:role_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['company'] = self.request.user.company
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, f'Role "{form.instance.name}" updated successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action'] = 'Update'
        context['permissions_by_category'] = self._get_permissions_by_category()
        return context
    
    def _get_permissions_by_category(self):
        """Same as CreateView"""
        return RoleCreateView._get_permissions_by_category(self)


class RoleDeleteView(CompanyAdminMixin, DeleteView):
    model = Role
    template_name = 'accounts/roles/confirm_delete.html'
    success_url = reverse_lazy('accounts:role_list')
    
    def delete(self, request, *args, **kwargs):
        role = self.get_object()
        role_name = role.name
        messages.success(self.request, f'Role "{role_name}" deleted successfully.')
        return super().delete(request, *args, **kwargs)


@login_required
@user_passes_test(is_company_admin)
def role_detail(request, pk):
    """View role details including assigned users and permissions"""
    role = get_object_or_404(Role, pk=pk, company=request.user.company)
    
    # Get users assigned to this role
    user_roles = UserRole.objects.filter(role=role).select_related('user')
    
    context = {
        'role': role,
        'user_roles': user_roles,
        'permissions_by_category': _get_role_permissions_by_category(role),
    }
    return render(request, 'accounts/roles/detail.html', context)


@login_required
@user_passes_test(is_company_admin)
def assign_role_to_users(request, pk):
    """Assign role to multiple users"""
    role = get_object_or_404(Role, pk=pk, company=request.user.company)
    
    if request.method == 'POST':
        user_ids = request.POST.getlist('users')
        
        # Clear existing assignments for this role
        UserRole.objects.filter(role=role).delete()
        
        # Create new assignments
        for user_id in user_ids:
            try:
                from .models import CustomUser
                user = CustomUser.objects.get(id=user_id, company=request.user.company)
                UserRole.objects.create(user=user, role=role)
            except CustomUser.DoesNotExist:
                continue
        
        messages.success(request, f'Role "{role.name}" assigned to {len(user_ids)} users.')
        return redirect('accounts:role_detail', pk=role.pk)
    
    # Get all company users
    from .models import CustomUser
    users = CustomUser.objects.filter(company=request.user.company).exclude(role='superadmin')
    
    # Get currently assigned users
    assigned_user_ids = UserRole.objects.filter(role=role).values_list('user_id', flat=True)
    
    context = {
        'role': role,
        'users': users,
        'assigned_user_ids': list(assigned_user_ids),
    }
    return render(request, 'accounts/roles/assign_users.html', context)


def _get_role_permissions_by_category(role):
    """Helper function to organize role permissions by category"""
    permissions = role.permissions.all()
    
    categories = {
        'User Management': [],
        'Company Management': [],
        'Extension Management': [],
        'Call Records': [],
        'Call Patterns': [],
        'Quota Management': [],
        'Other': []
    }
    
    for perm in permissions:
        categorized = False
        if 'user' in perm.codename or 'customuser' in perm.codename:
            categories['User Management'].append(perm)
            categorized = True
        elif 'company' in perm.codename:
            categories['Company Management'].append(perm)
            categorized = True
        elif 'extension' in perm.codename:
            categories['Extension Management'].append(perm)
            categorized = True
        elif 'callrecord' in perm.codename:
            categories['Call Records'].append(perm)
            categorized = True
        elif 'callpattern' in perm.codename:
            categories['Call Patterns'].append(perm)
            categorized = True
        elif 'quota' in perm.codename or 'userquota' in perm.codename:
            categories['Quota Management'].append(perm)
            categorized = True
        
        if not categorized:
            categories['Other'].append(perm)
    
    # Remove empty categories
    return {k: v for k, v in categories.items() if v}