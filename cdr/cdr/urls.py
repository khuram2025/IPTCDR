
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('billing/', include('billing.urls', namespace='billing')),
    path('realtime/', include('realtime.urls', namespace='realtime')),
    path('security/', include('security.urls', namespace='security')),
    path('', include('cdr3cx.urls')),
    path('accounts/', include('accounts.urls')),
    path('notifications/', include('notifications.urls', namespace='notifications')),

]
