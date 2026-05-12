from django.urls import path

from . import views

app_name = 'realtime'

urlpatterns = [
    path('wallboard/',           views.wallboard,            name='wallboard'),
    path('wallboard/projection/', views.wallboard_projection, name='wallboard_projection'),
    path('wallboard/heatmap/',   views.heatmap_view,         name='heatmap'),
    path('wallboard/heatmap.json', views.heatmap_data,       name='heatmap_data'),
]
