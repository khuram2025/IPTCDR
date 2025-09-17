from django.urls import path
from .views import signup, login_view, account_activation_sent, activate, reset_password, verify_otp, set_new_password
from . import views, role_views
app_name = 'accounts' 

urlpatterns = [
    path('signup/', signup, name='signup'),
    path('login/', login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
    path('test-login/', views.test_login, name='test_login'),

    # Super Admin Dashboard & CRUD
    path('superadmin/', views.superadmin_dashboard, name='superadmin_dashboard'),
    path('superadmin/company/create/', views.company_create, name='company_create'),
    path('superadmin/company/<int:company_id>/edit/', views.company_edit, name='company_edit'),
    path('superadmin/company/<int:company_id>/delete/', views.company_delete, name='company_delete'),
    path('superadmin/admin/create/', views.admin_create, name='admin_create'),
    path('superadmin/admin/<int:user_id>/edit/', views.admin_edit, name='admin_edit'),
    path('superadmin/admin/<int:user_id>/delete/', views.admin_delete, name='admin_delete'),

    # Company Admin Dashboard & CRUD
    path('company-admin/', views.company_admin_dashboard, name='company_admin_dashboard'),
    path('company-admin/user/create/', views.company_user_create, name='company_user_create'),
    path('company-admin/user/<int:user_id>/edit/', views.company_user_edit, name='company_user_edit'),
    path('company-admin/user/<int:user_id>/delete/', views.company_user_delete, name='company_user_delete'),

    # Role Management
    path('roles/', role_views.RoleListView.as_view(), name='role_list'),
    path('roles/create/', role_views.RoleCreateView.as_view(), name='role_create'),
    path('roles/<int:pk>/', role_views.role_detail, name='role_detail'),
    path('roles/<int:pk>/edit/', role_views.RoleUpdateView.as_view(), name='role_edit'),
    path('roles/<int:pk>/delete/', role_views.RoleDeleteView.as_view(), name='role_delete'),
    path('roles/<int:pk>/assign-users/', role_views.assign_role_to_users, name='role_assign_users'),

    # Existing auth & password routes
    path('account_activation_sent/', account_activation_sent, name='account_activation_sent'),
    path('activate/<uidb64>/<token>/', activate, name='activate'),
    path('forgot-password/', views.forgot_password_request, name='forgot_password_request'),
    path('forgot-password/otp/', views.forgot_password_otp, name='forgot_password_otp'),
    path('forgot-password/new/', views.forgot_password_new_password, name='forgot_password_new_password'),
    path('change-password/', views.change_password, name='change_password'),
]
