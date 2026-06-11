from django.urls import path
from .views import receive_cdr
from . import views, views_api, quota_views, views_reports, callpattern_views, callcenter_views, report_views, public_views, extension_views
from . import views as cdr_views


app_name = 'cdr3cx' 

urlpatterns = [
    path('toggle-external-call/', quota_views.toggle_external_call, name='toggle_external_call'),
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

    # Public marketing site (SEO) — connect.zentryc.com
    path('', public_views.home, name='landing_page'),
    path('features/', public_views.features, name='public_features'),
    path('pricing/', public_views.pricing, name='public_pricing'),
    path('about/', public_views.about, name='public_about'),
    path('contact/', public_views.contact, name='public_contact'),
    path('kb/', public_views.kb_index, name='kb_index'),
    path('kb/<slug:slug>/', public_views.kb_article, name='kb_article'),
    path('robots.txt', public_views.robots_txt, name='robots_txt'),
    path('sitemap.xml', public_views.sitemap_xml, name='sitemap_xml'),

    path('dashboard/', views.dashboard, name='dashboard'),
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

    # Extension directory (3CX-synced) — list + detail + on-demand sync
    path('extensions/', extension_views.extension_list, name='extension_list'),
    path('extensions/sync/', extension_views.sync_extensions_now, name='extension_sync'),
    path('extensions/<int:pk>/', extension_views.extension_detail, name='extension_detail'),

    # Call Pattern URLs for Company Admin
    path('callpatterns/', callpattern_views.CallPatternListView.as_view(), name='callpattern-list'),
    path('callpatterns/create/', callpattern_views.CallPatternCreateView.as_view(), name='callpattern-create'),
    path('callpatterns/<int:pk>/edit/', callpattern_views.CallPatternUpdateView.as_view(), name='callpattern-edit'),
    path('callpatterns/<int:pk>/delete/', callpattern_views.CallPatternDeleteView.as_view(), name='callpattern-delete'),

    path('top-extensions/', views.top_extensions, name='top_extensions'),
    path('top-extensions/excel-report/', views.generate_excel_report, name='top_extensions_excel_report'),
    path('top-extensions/pdf/', views.top_extensions_pdf_report, name='top_extensions_pdf_report'),

    path('sales-reports/', views.sales_reports, name='sales_reports'),

    path('outgoing_international/excel/', views_reports.export_international_calls_excel, name='export_international_calls_excel'),
    path('outgoing_international/pdf/', views_reports.export_international_calls_pdf, name='export_international_calls_pdf'),
    
    # Call Center URLs
    path('call-center/', callcenter_views.call_center_dashboard, name='call_center_dashboard'),
    path('call-center/agent/<str:agent_extension>/', callcenter_views.agent_details, name='agent_details'),
    path('call-center/queue/<str:queue_dn>/', callcenter_views.queue_details, name='queue_details'),
    path('call-center/missed-calls/', callcenter_views.missed_calls_details, name='missed_calls_details'),
    path('call-center/call-back-tracking/', callcenter_views.call_back_tracking, name='call_back_tracking'),
    path('call-center/wallboard/', callcenter_views.callcenter_wallboard, name='callcenter_wallboard'),
    path('call-center/wallboard/data/', callcenter_views.wallboard_data, name='wallboard_data'),
    # P3.2 — Report catalog + per-call drill-down
    path('call-center/reports/catalog/', report_views.report_catalog, name='report_catalog'),
    path('call-center/call/<int:pk>/', callcenter_views.call_detail, name='call_detail'),
    # P3.1 — Scheduled reports
    path('call-center/reports/', report_views.report_list, name='report_list'),
    path('call-center/reports/new/', report_views.report_create, name='report_create'),
    path('call-center/reports/<int:pk>/edit/', report_views.report_edit, name='report_edit'),
    path('call-center/reports/<int:pk>/delete/', report_views.report_delete, name='report_delete'),
    path('call-center/reports/<int:pk>/run/', report_views.report_run_now, name='report_run_now'),
    path('call-center/reports/generate/', report_views.report_generate_now, name='report_generate_now'),
    path('call-center/reports/run/<int:pk>/download/', report_views.report_download, name='report_download'),
]
