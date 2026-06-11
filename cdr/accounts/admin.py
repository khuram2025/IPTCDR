from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Company, Extension, SMTPSettings
from .forms import CustomUserCreationForm, CustomUserChangeForm

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ('email', 'role', 'company', 'is_staff', 'is_active')
    list_filter = ('role', 'company', 'is_staff', 'is_active')
    fieldsets = (
        (None, {'fields': ('email', 'password', 'company', 'role')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'company', 'role', 'password1', 'password2', 'is_staff', 'is_active', 'groups', 'user_permissions')}
        ),
    )
    search_fields = ('email',)
    ordering = ('email',)

admin.site.register(CustomUser, CustomUserAdmin)

from django import forms
from django.urls import path
from django.shortcuts import redirect, render
from django.contrib import messages
from cdr.email_utils import SMTPClient

@admin.register(SMTPSettings)
class SMTPSettingsAdmin(admin.ModelAdmin):
    list_display = ('host', 'port', 'username', 'from_email', 'is_active', 'updated_at')
    search_fields = ('host', 'username', 'from_email')
    list_filter = ('is_active',)
    readonly_fields = ('updated_at',)
    fieldsets = (
        (None, {
            'fields': ('host', 'port', 'use_tls', 'use_ssl', 'username', 'password', 'from_email', 'is_active')
        }),
        ('Timestamps', {'fields': ('updated_at',)}),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['password'].widget.attrs['type'] = 'password'
        return form

    def has_module_permission(self, request):
        return request.user.is_superuser
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
    def has_add_permission(self, request):
        return request.user.is_superuser
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('<int:smtpsettings_id>/test-email/', self.admin_site.admin_view(self.test_email), name='accounts_smtpsettings_test_email'),
        ]
        return custom_urls + urls

    def test_email(self, request, smtpsettings_id):
        smtp_obj = SMTPSettings.objects.get(pk=smtpsettings_id)
        class TestEmailForm(forms.Form):
            recipient = forms.EmailField(label="Recipient Email", initial=request.user.email)
            subject = forms.CharField(label="Subject", initial="SMTP Test Email", max_length=255)
            body = forms.CharField(label="Body", initial="This is a test email to verify SMTP settings.", widget=forms.Textarea)
        if request.method == "POST":
            form = TestEmailForm(request.POST)
            if form.is_valid():
                try:
                    SMTPClient.send_email(
                        subject=form.cleaned_data['subject'],
                        body=form.cleaned_data['body'],
                        to=[form.cleaned_data['recipient']],
                        from_email=smtp_obj.from_email,
                        smtp_override=smtp_obj
                    )
                    self.message_user(request, f"Test email sent successfully to {form.cleaned_data['recipient']}", level=messages.SUCCESS)
                except Exception as e:
                    self.message_user(request, f"Failed to send test email: {e}", level=messages.ERROR)
                return redirect(f"../../{smtpsettings_id}/change/")
        else:
            form = TestEmailForm()
        context = dict(
            self.admin_site.each_context(request),
            form=form,
            smtp_obj=smtp_obj,
            title="Send Test Email",
        )
        return render(request, "admin/accounts/smtpsettings/test_email.html", context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        # Compose the full URL for the test email view
        extra_context['test_email_url'] = f"{object_id}/test-email/"
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'phone', 'listening_port', 'pbx_source_ips', 'pbx_api_url')
    search_fields = ('name', 'address', 'phone')


from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Extension
from .resources import ExtensionResource

@admin.register(Extension)
class ExtensionAdmin(ImportExportModelAdmin):
    resource_class = ExtensionResource
    list_display = ('extension', 'full_name', 'email', 'company')
    search_fields = ('extension', 'full_name', 'email', 'company__name')
    list_filter = ('company',)
