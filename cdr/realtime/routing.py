"""WebSocket URL → consumer routing for the realtime app."""
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/wallboard/$', consumers.WallboardConsumer.as_asgi()),
]
