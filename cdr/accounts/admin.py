from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Company
from .forms import CustomUserCreationForm, CustomUserChangeForm

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ('email', 'company', 'is_staff', 'is_active')
    list_filter = ('company', 'is_staff', 'is_active')
    fieldsets = (
        (None, {'fields': ('email', 'password', 'company')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'company', 'password1', 'password2', 'is_staff', 'is_active', 'groups', 'user_permissions')}
        ),
    )
    search_fields = ('email',)
    ordering = ('email',)

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Company)
