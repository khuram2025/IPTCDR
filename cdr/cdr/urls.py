
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('cdr3cx.urls')),
    path('accounts/', include('accounts.urls')),
    path('notifications/', include('notifications.urls', namespace='notifications')),

]
