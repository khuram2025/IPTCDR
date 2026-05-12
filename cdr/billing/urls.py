from django.urls import path

from . import views

app_name = 'billing'

urlpatterns = [
    path('fraud-incidents/',                    views.fraud_incident_dashboard, name='fraud_incidents'),
    path('fraud-incidents/<int:incident_id>/acknowledge/',  views.acknowledge_incident,  name='acknowledge_incident'),
    path('fraud-incidents/<int:incident_id>/resolve/',      views.resolve_incident,      name='resolve_incident'),
    path('fraud-incidents/<int:incident_id>/false-positive/', views.mark_false_positive, name='false_positive_incident'),

    # Public lead-gen tool
    path('free-fraud-audit/', views.free_fraud_audit, name='free_fraud_audit'),
]
