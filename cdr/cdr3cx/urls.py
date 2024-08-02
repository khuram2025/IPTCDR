from django.urls import path
from .views import receive_cdr
from . import views

app_name = 'cdr3cx' 

urlpatterns = [
    path('cdr', receive_cdr, name='receive_cdr'),
    path('get-caller/', views.get_caller_record, name='get_caller_record'),
    path('home/', views.home, name='home'),
    path('', views.dashboard, name='dashboard'),
    path('update_country/<int:record_id>/', views.update_country, name='update_country'),
    path('all_calls/', views.all_calls_view, name='all_calls'),

    path('outgoing/', views.outgoingExtCalls, name='outgoing'),
    path('incoming/', views.incomingCalls, name='incoming'),

    path('outgoing_international/', views.outgoingInternationalCalls, name='outgoing_international'),

    path('local_calls/', views.local_calls_view, name='local_calls'),
    path('national_calls/', views.national_calls_view, name='national_calls'),
    path('international_calls/', views.international_calls_view, name='international_calls'),
]
