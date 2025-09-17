from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, PasswordResetForm, AuthenticationForm
from django.contrib.auth.models import Permission
from .models import Company, CustomUser, Role

class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'address', 'phone', 'listening_port']

class CustomUserCreationForm(UserCreationForm):
    company = forms.ModelChoiceField(queryset=Company.objects.all(), required=False)
    role = forms.ChoiceField(choices=CustomUser.ROLE_CHOICES, required=True)
    custom_roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select additional custom roles for this user"
    )

    class Meta:
        model = CustomUser
        fields = ('email', 'company', 'role', 'custom_roles', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        
        if company:
            self.fields['custom_roles'].queryset = Role.objects.filter(
                company=company, 
                is_active=True
            ).order_by('name')

    def save(self, commit=True):
        user = super().save(commit=False)
        # Assign the default company "Channab" if no company is provided
        if not user.company:
            user.company = Company.objects.get_or_create(name="Channab")[0]
        else:
            user.company, created = Company.objects.get_or_create(name=user.company.name)
        user.role = self.cleaned_data['role']
        if commit:
            user.save()
            self.save_custom_roles(user)
        return user
    
    def save_custom_roles(self, user):
        """Helper method to save custom roles"""
        if self.cleaned_data.get('custom_roles'):
            from .models import UserRole
            for role in self.cleaned_data['custom_roles']:
                UserRole.objects.get_or_create(
                    user=user,
                    role=role
                )


class CustomUserChangeForm(UserChangeForm):
    role = forms.ChoiceField(choices=CustomUser.ROLE_CHOICES, required=True)
    custom_roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select additional custom roles for this user"
    )
    
    class Meta:
        model = CustomUser
        fields = ('email', 'company', 'role', 'custom_roles', 'password', 'is_active', 'is_staff', 'groups', 'user_permissions')

    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        
        if company:
            self.fields['custom_roles'].queryset = Role.objects.filter(
                company=company, 
                is_active=True
            ).order_by('name')
            
            # Set initial values for custom roles if editing existing user
            if self.instance and self.instance.pk:
                from .models import UserRole
                current_roles = UserRole.objects.filter(
                    user=self.instance
                ).values_list('role', flat=True)
                self.fields['custom_roles'].initial = current_roles

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            self.save_custom_roles(user)
        return user
    
    def save_custom_roles(self, user):
        """Helper method to save custom roles"""
        from .models import UserRole
        # Clear existing custom roles
        UserRole.objects.filter(user=user).delete()
        
        # Add new custom roles
        if self.cleaned_data.get('custom_roles'):
            for role in self.cleaned_data['custom_roles']:
                UserRole.objects.create(
                    user=user,
                    role=role
                )

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}), label="Email")
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), label="Password")
    remember = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}), label="Remember Me")

class CustomPasswordResetForm(PasswordResetForm):
    email = forms.EmailField()

class ForgotPasswordRequestForm(forms.Form):
    email = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter your email'}))

class ForgotPasswordOTPForm(forms.Form):
    otp_code = forms.CharField(label="OTP Code", max_length=6, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter the OTP sent to your email'}))

class ForgotPasswordNewPasswordForm(forms.Form):
    new_password1 = forms.CharField(label="New Password", widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New password'}))
    new_password2 = forms.CharField(label="Confirm Password", widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'}))
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('new_password1') != cleaned_data.get('new_password2'):
            raise forms.ValidationError('Passwords do not match')
        return cleaned_data

class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(label="Current Password", widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Current password'}))
    new_password1 = forms.CharField(label="New Password", widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New password'}))
    new_password2 = forms.CharField(label="Confirm New Password", widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'}))
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('new_password1') != cleaned_data.get('new_password2'):
            raise forms.ValidationError('New passwords do not match')
        return cleaned_data


class RoleForm(forms.ModelForm):
    """Form for creating and editing custom roles"""
    
    # Custom permission categories for better UX
    PERMISSION_CATEGORIES = {
        'User Management': ['add_customuser', 'change_customuser', 'delete_customuser', 'view_customuser'],
        'Company Management': ['change_company', 'view_company'],
        'Extension Management': ['add_extension', 'change_extension', 'delete_extension', 'view_extension'],
        'Call Records': ['view_callrecord', 'add_callrecord', 'change_callrecord'],
        'Call Patterns': ['add_callpattern', 'change_callpattern', 'delete_callpattern', 'view_callpattern'],
        'Quota Management': ['add_quota', 'change_quota', 'delete_quota', 'view_quota',
                           'add_userquota', 'change_userquota', 'delete_userquota', 'view_userquota'],
        'Reporting': ['view_reports', 'export_data'],
    }
    
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select permissions for this role"
    )
    
    class Meta:
        model = Role
        fields = ['name', 'description', 'permissions', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Sales Manager, Call Center Agent'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe what this role can do...'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        
        if company:
            # Filter permissions to relevant ones for this system
            relevant_apps = ['accounts', 'cdr3cx']
            self.fields['permissions'].queryset = Permission.objects.filter(
                content_type__app_label__in=relevant_apps
            ).order_by('content_type__app_label', 'codename')
    
    def clean_name(self):
        name = self.cleaned_data['name']
        # Additional validation can be added here
        return name


class UserRoleAssignmentForm(forms.Form):
    """Form for assigning custom roles to users"""
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select roles for this user"
    )
    
    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        
        if company:
            self.fields['roles'].queryset = Role.objects.filter(
                company=company, 
                is_active=True
            ).order_by('name')

