from django.urls import path
from .views import signup, login_view, account_activation_sent, activate, reset_password, verify_otp, set_new_password
from . import views
app_name = 'accounts' 

urlpatterns = [
    path('signup/', signup, name='signup'),
    path('login/', login_view, name='login'),
    path('account_activation_sent/', account_activation_sent, name='account_activation_sent'),
    path('activate/<uidb64>/<token>/', activate, name='activate'),
    path('reset_password/', reset_password, name='reset_password'),
    path('verify_otp/<int:user_id>/', verify_otp, name='verify_otp'),
    path('set_new_password/<int:user_id>/', set_new_password, name='set_new_password'),
     path('logout/', views.logout_view, name='logout'), 
]
