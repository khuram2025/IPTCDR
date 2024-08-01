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
