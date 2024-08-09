from django.urls import path
from .views import receive_cdr
from . import views

app_name = 'cdr3cx' 

urlpatterns = [
    path('cdr', receive_cdr, name='receive_cdr'),
    path('get-caller/', views.get_caller_record, name='get_caller_record'),

    path('home/', views.home, name='home'),
    path('aboutus/', views.aboutus, name='aboutus'),

    path('', views.dashboard, name='dashboard'),
    path('update_country/<int:record_id>/', views.update_country, name='update_country'),
    path('all_calls/', views.all_calls_view, name='all_calls'),

    path('outgoing/', views.outgoingExtCalls, name='outgoing'),
    path('incoming/', views.incomingCalls, name='incoming'),
    path('update-call-stats/', views.update_call_stats, name='update_call_stats'),
    path('summary/', views.call_record_summary_view, name='callrecord_summary'),
  


    path('outgoing_international/', views.outgoingInternationalCalls, name='outgoing_international'),
    path('caller-calls/<str:caller_number>/', views.caller_calls_view, name='caller_calls'),


    path('local_calls/', views.local_calls_view, name='local_calls'),
    path('national_calls/', views.national_calls_view, name='national_calls'),
    path('international_calls/', views.international_calls_view, name='international_calls'),
    path('international-calls/<slug:country_slug>/', views.country_specific_calls_view, name='country_specific_calls'),

]
