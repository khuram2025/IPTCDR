from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, PasswordResetForm, AuthenticationForm
from .models import Company, CustomUser

class CustomUserCreationForm(UserCreationForm):
    company = forms.ModelChoiceField(queryset=Company.objects.all(), required=False)

    class Meta:
        model = CustomUser
        fields = ('email', 'company', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        # Assign the default company "Channab" if no company is provided
        if not user.company:
            user.company = Company.objects.get_or_create(name="Channab")[0]
        else:
            user.company, created = Company.objects.get_or_create(name=user.company.name)
        if commit:
            user.save()
        return user


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'company', 'password', 'is_active', 'is_staff', 'groups', 'user_permissions')

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

