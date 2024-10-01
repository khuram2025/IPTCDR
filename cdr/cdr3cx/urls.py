from django.urls import path
from .views import receive_cdr
from . import views, views_api, quota_views, views_reports
from . import views as cdr_views


app_name = 'cdr3cx' 

urlpatterns = [
    path('cdr', receive_cdr, name='receive_cdr'),
    path('get-caller/', views.get_caller_record, name='get_caller_record'),
    # API Related start 
    path('get-3cx-version/', views_api.get_3cx_version, name='get_3cx_version'),
    path('get_users/', views_api.get_users, name='get_users'),
    path('get-user-groups/<int:user_id>/', views_api.get_user_groups, name='get_user_groups'),
    # END


    path('home/', views.home, name='home'),
    path('ipt_landing/', views.ipt_landing, name='ipt_landing'),
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


    path('quotas/', quota_views.QuotaListView.as_view(), name='quota_list'),
    path('quotas/create/', quota_views.QuotaCreateView.as_view(), name='quota_create'),
    path('quotas/<int:pk>/update/', quota_views.QuotaUpdateView.as_view(), name='quota_update'),
    path('quotas/<int:pk>/delete/', quota_views.QuotaDeleteView.as_view(), name='quota_delete'),
    path('quotas/assign/', quota_views.assign_quota, name='assign_quota'),
    path('quotas/usage/', quota_views.quota_usage, name='quota_usage'),
    path('extension/<int:extension_id>/add-balance/', quota_views.add_balance, name='add_balance'),
    path('quotas/send_email/<int:extension_id>/', quota_views.send_quota_email, name='send_quota_email'),  # New URL pattern

    path('top-extensions/', views.top_extensions, name='top_extensions'),
    path('top-extensions/excel-report/', views.generate_excel_report, name='top_extensions_excel_report'),
    path('top-extensions/pdf/', views.top_extensions_pdf_report, name='top_extensions_pdf_report'),


    path('outgoing_international/excel/', views_reports.export_international_calls_excel, name='export_international_calls_excel'),
    path('outgoing_international/pdf/', views_reports.export_international_calls_pdf, name='export_international_calls_pdf'),
]
