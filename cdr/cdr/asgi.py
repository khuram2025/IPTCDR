"""ASGI config — routes HTTP through Django and WebSockets through Channels.

The realtime app's ``routing`` module enumerates every WebSocket URL pattern.
Authentication is handled via Django's session middleware so the consumer
sees ``request.user`` and can scope to ``user.company``.
"""
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cdr.settings')

# Initialise Django before importing app code that needs the ORM.
django_asgi_app = get_asgi_application()

from realtime.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    ),
})
