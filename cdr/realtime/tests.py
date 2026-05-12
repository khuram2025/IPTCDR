"""Wallboard tests — snapshot, HTTP views, WebSocket consumer + signal fan-out."""
import json
from decimal import Decimal
from unittest.mock import patch

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TestCase, TransactionTestCase
from django.test.utils import override_settings

from accounts.models import Company, Currency, CustomUser
from cdr3cx.models import CallRecord

from .snapshot import build, build_heatmap


def _mute_webhooks():
    return patch('api.services.webhooks.requests.post', return_value=type(
        'R', (), {'status_code': 200, 'text': 'OK'})())


class SnapshotBuilderTests(TestCase):

    def setUp(self):
        self.sar, _ = Currency.objects.get_or_create(
            code='SAR', defaults={'name': 'Saudi Riyal', 'symbol': 'ر.س'},
        )
        self.company = Company.objects.create(name='Snap Co', currency=self.sar, country_code='SA')
        self._wh = _mute_webhooks(); self._wh.start()

    def tearDown(self):
        self._wh.stop()

    def test_empty_snapshot_has_zeroes(self):
        snap = build(self.company)
        self.assertEqual(snap['counters']['total'], 0)
        self.assertEqual(snap['counters']['answered'], 0)
        self.assertEqual(snap['counters']['answer_rate'], 0)
        self.assertEqual(len(snap['hourly']), 24)

    def test_snapshot_counts_calls(self):
        from django.utils import timezone
        now = timezone.now()
        for i in range(5):
            CallRecord.objects.create(
                company=self.company, source_pbx='3cx', caller='2001',
                callee='0501234567', duration=60, call_time=now,
            )
        snap = build(self.company)
        self.assertEqual(snap['counters']['total'], 5)
        self.assertEqual(snap['counters']['answered'], 5)
        self.assertEqual(snap['counters']['answer_rate'], 100.0)

    def test_snapshot_distinguishes_missed(self):
        from django.utils import timezone
        now = timezone.now()
        CallRecord.objects.create(company=self.company, source_pbx='3cx',
                                   caller='2001', callee='0501234567',
                                   duration=60, call_time=now)
        CallRecord.objects.create(company=self.company, source_pbx='3cx',
                                   caller='2001', callee='0501234567',
                                   reason_terminated='NoAnswer', call_time=now)
        snap = build(self.company)
        self.assertEqual(snap['counters']['missed'], 1)

    def test_heatmap_shape(self):
        h = build_heatmap(self.company, days=7)
        self.assertEqual(len(h['grid']), 7)
        self.assertEqual(len(h['grid'][0]), 24)


class WallboardViewTests(TestCase):

    def setUp(self):
        self.sar, _ = Currency.objects.get_or_create(code='SAR', defaults={'name': 'SAR', 'symbol': 'ر.س'})
        self.company = Company.objects.create(name='WBCo', currency=self.sar, country_code='SA')
        self.user = CustomUser.objects.create_user(email='wb@ex.com', password='x', company=self.company.name)
        self._wh = _mute_webhooks(); self._wh.start()

    def tearDown(self):
        self._wh.stop()

    def test_wallboard_requires_login(self):
        r = self.client.get('/realtime/wallboard/')
        self.assertIn(r.status_code, (302, 301))

    def test_wallboard_renders_for_logged_in_user(self):
        self.client.force_login(self.user)
        r = self.client.get('/realtime/wallboard/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Live Wallboard', r.content)
        # snapshot should be embedded as JSON literal
        self.assertIn(b'"counters"', r.content)

    def test_projection_renders(self):
        self.client.force_login(self.user)
        r = self.client.get('/realtime/wallboard/projection/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Projection', r.content)

    def test_heatmap_data_endpoint(self):
        self.client.force_login(self.user)
        r = self.client.get('/realtime/wallboard/heatmap.json?days=7')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body['grid']), 7)
        self.assertEqual(len(body['grid'][0]), 24)


@override_settings(CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
class WallboardConsumerTests(TransactionTestCase):
    """Async WebSocket round-trip — connect, receive snapshot, then a live event.

    Uses TransactionTestCase because TestCase's atomic transaction conflicts
    with the database_sync_to_async pattern used by Channels consumers.
    """

    serialized_rollback = False

    async def _setup(self):
        self.user = await database_sync_to_async(self._make_user)()

    def _make_user(self):
        sar, _ = Currency.objects.get_or_create(code='SAR', defaults={'name': 'SAR', 'symbol': 'ر.س'})
        company = Company.objects.create(name='WS Co', currency=sar, country_code='SA')
        return CustomUser.objects.create_user(email='ws@ex.com', password='x', company=company.name)

    async def test_anonymous_connection_rejected(self):
        from cdr.asgi import application
        comm = WebsocketCommunicator(application, '/ws/wallboard/')
        connected, _ = await comm.connect()
        self.assertFalse(connected)

    async def test_authenticated_connect_receives_snapshot(self):
        await self._setup()
        from cdr.asgi import application
        comm = WebsocketCommunicator(application, '/ws/wallboard/')
        comm.scope['user'] = self.user
        connected, _ = await comm.connect()
        self.assertTrue(connected)

        msg = await comm.receive_json_from(timeout=5)
        self.assertEqual(msg['type'], 'snapshot')
        self.assertIn('counters', msg['data'])
        await comm.disconnect()

    async def test_call_save_pushes_live_event(self):
        await self._setup()
        from cdr.asgi import application
        comm = WebsocketCommunicator(application, '/ws/wallboard/')
        comm.scope['user'] = self.user
        connected, _ = await comm.connect()
        self.assertTrue(connected)

        # Drain initial snapshot
        await comm.receive_json_from(timeout=5)

        # Mute webhooks then save a call from sync world
        with _mute_webhooks():
            await database_sync_to_async(CallRecord.objects.create)(
                company=self.user.company, source_pbx='3cx',
                caller='2001', callee='0501234567', duration=60,
            )

        msg = await comm.receive_json_from(timeout=5)
        self.assertEqual(msg['type'], 'call.completed')
        self.assertEqual(msg['data']['caller'], '2001')
        await comm.disconnect()
