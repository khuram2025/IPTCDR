from django.urls import path
from .views import signup, login_view, account_activation_sent, activate, reset_password, verify_otp, set_new_password
from . import views
app_name = 'accounts' 

urlpatterns = [
    path('signup/', signup, name='signup'),
    path('login/', login_view, name='login'),
    path('account_activation_sent/', account_activation_sent, name='account_activation_sent'),
    path('activate/<uidb64>/<token>/', activate, name='activate'),
    path('forgot-password/', views.forgot_password_request, name='forgot_password_request'),
    path('forgot-password/otp/', views.forgot_password_otp, name='forgot_password_otp'),
    path('forgot-password/new/', views.forgot_password_new_password, name='forgot_password_new_password'),
    path('change-password/', views.change_password, name='change_password'),
    path('logout/', views.logout_view, name='logout'),
]
