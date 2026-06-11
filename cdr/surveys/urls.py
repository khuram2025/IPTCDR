from django.urls import path

from . import views

app_name = 'surveys'

urlpatterns = [
    path('call-center/surveys/', views.survey_dashboard, name='dashboard'),
    path('call-center/surveys/responses/', views.survey_responses, name='responses'),
    path('call-center/surveys/responses/<int:pk>/', views.survey_response_detail, name='response_detail'),
    path('call-center/surveys/settings/', views.survey_settings, name='settings'),
    path('call-center/surveys/campaigns/<int:pk>/regenerate-token/', views.regenerate_token, name='regenerate_token'),
]
