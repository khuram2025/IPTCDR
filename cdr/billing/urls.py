from django.urls import path
from .views import call_rate_list, call_rate_add, get_example_number
from . import views
app_name = 'billing' 

urlpatterns = [
    path('call-rates/', call_rate_list, name='call_rate_list'),
    path('call-rates/add/', call_rate_add, name='call_rate_add'),
    path('get-example-number/', get_example_number, name='get_example_number'),
    path('user-quotas/', views.user_quota_list, name='user_quota_list'),
]
