"""WebSocket consumers.

Each authenticated user joins a group keyed by their ``company.pk``.
Events published to that group reach every wallboard the company has open.

Public-share mode (non-auth) connects via signed token in the URL —
deferred until P2 (white-label / sharing). For now, login required.
"""
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer


def group_name(company_id: int) -> str:
    return f'wallboard.company.{company_id}'


class WallboardConsumer(AsyncJsonWebsocketConsumer):
    """Real-time KPI consumer scoped per company."""

    async def connect(self):
        user = self.scope.get('user')
        if not user or user.is_anonymous:
            await self.close(code=4401)  # 4401 = Unauthorized
            return
        company = await database_sync_to_async(lambda: user.company)()
        if company is None:
            await self.close(code=4403)  # 4403 = Forbidden
            return

        self.company_id = company.pk
        self.group = group_name(company.pk)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

        # Send an initial snapshot so the freshly-opened wallboard isn't blank.
        snapshot = await database_sync_to_async(self._snapshot)(company)
        await self.send_json({'type': 'snapshot', 'data': snapshot})

    async def disconnect(self, close_code):
        if hasattr(self, 'group'):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Clients may request a refreshed snapshot
        if content.get('action') == 'refresh':
            user = self.scope.get('user')
            company = await database_sync_to_async(lambda: user.company)()
            snapshot = await database_sync_to_async(self._snapshot)(company)
            await self.send_json({'type': 'snapshot', 'data': snapshot})

    # ---- group event handlers -----------------------------------------
    # Channel layer dispatches 'wallboard.event' messages to this method.

    async def wallboard_event(self, event):
        await self.send_json({'type': event.get('event_type', 'event'),
                              'data': event.get('payload', {})})

    # ------------------------------------------------------------------

    @staticmethod
    def _snapshot(company):
        from .snapshot import build
        return build(company)
