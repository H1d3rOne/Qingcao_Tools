import asyncio
from fastapi.testclient import TestClient

from app.main import app
from app.modules.xianyu.schemas import XianyuChatProfile


class FakeChatClient:
    def __init__(self):
        self.profile = XianyuChatProfile(user_id='111', main_user_id='111', domain='goofish', display_name='卖家', avatar='')
        self._queue = asyncio.Queue()
        self._queue.put_nowait({'lwp': '/s/sync', 'headers': {}, 'body': {'syncPushPackage': {'data': []}}})
        self.close_calls = 0

    async def next_push(self):
        return await self._queue.get()

    def subscribe_pushes(self):
        return self._queue

    def unsubscribe_pushes(self, queue):
        return None

    async def close(self):
        self.close_calls += 1
        return None


class FakeService:
    def __init__(self):
        self.ai_called = 0

    async def open_chat_ws_client(self):
        return FakeChatClient()

    def decode_chat_push(self, payload):
        return {'type': 'sync', 'items': []}

    async def maybe_auto_reply_from_decoded_push(self, profile, decoded):
        self.ai_called += 1
        return None

    def _require_xianyu_cookie(self):
        return 'cookie'

    def _create_http_client(self, cookie):
        raise RuntimeError('should not be called in test')


def test_xianyu_chat_ws_invokes_ai_handler_for_pushes(monkeypatch):
    from app.api.v1 import xianyu as xianyu_api

    fake_service = FakeService()
    monkeypatch.setattr(xianyu_api, 'get_xianyu_service', lambda: fake_service)
    monkeypatch.setattr(xianyu_api, 'is_xianyu_cookie_configured', lambda: True)

    client = TestClient(app)
    with client.websocket_connect('/api/v1/xianyu/chat/ws') as websocket:
        connected = websocket.receive_json()
        pushed = websocket.receive_json()
        websocket.send_json({'action': 'close'})
        assert connected['type'] == 'connected'
        assert pushed['type'] == 'push'

    assert fake_service.ai_called == 1


def test_xianyu_chat_ws_does_not_close_shared_client(monkeypatch):
    from app.api.v1 import xianyu as xianyu_api

    class FakeSharedService(FakeService):
        def __init__(self):
            super().__init__()
            self._shared_chat_client = FakeChatClient()

        async def open_chat_ws_client(self):
            return self._shared_chat_client

    fake_service = FakeSharedService()
    monkeypatch.setattr(xianyu_api, 'get_xianyu_service', lambda: fake_service)
    monkeypatch.setattr(xianyu_api, 'is_xianyu_cookie_configured', lambda: True)

    client = TestClient(app)
    with client.websocket_connect('/api/v1/xianyu/chat/ws') as websocket:
        assert websocket.receive_json()['type'] == 'connected'
        assert websocket.receive_json()['type'] == 'push'
        websocket.send_json({'action': 'close'})
        assert websocket.receive_json()['type'] == 'disconnected'

    assert fake_service._shared_chat_client.close_calls == 0


def test_xianyu_chat_ws_relays_pushes_from_shared_subscription(monkeypatch):
    from app.api.v1 import xianyu as xianyu_api

    class FakeSubscribedClient(FakeChatClient):
        def __init__(self):
            super().__init__()
            self.subscribe_calls = 0
            self.unsubscribe_calls = 0

        async def next_push(self):
            raise AssertionError('frontend websocket should subscribe to shared pushes instead of consuming next_push')

        def subscribe_pushes(self):
            self.subscribe_calls += 1
            return self._queue

        def unsubscribe_pushes(self, queue):
            self.unsubscribe_calls += 1

    class FakeSharedService(FakeService):
        def __init__(self):
            super().__init__()
            self._shared_chat_client = FakeSubscribedClient()

        async def open_chat_ws_client(self):
            return self._shared_chat_client

    fake_service = FakeSharedService()
    monkeypatch.setattr(xianyu_api, 'get_xianyu_service', lambda: fake_service)
    monkeypatch.setattr(xianyu_api, 'is_xianyu_cookie_configured', lambda: True)

    client = TestClient(app)
    with client.websocket_connect('/api/v1/xianyu/chat/ws') as websocket:
        assert websocket.receive_json()['type'] == 'connected'
        assert websocket.receive_json()['type'] == 'push'
        websocket.send_json({'action': 'close'})
        assert websocket.receive_json()['type'] == 'disconnected'

    assert fake_service._shared_chat_client.subscribe_calls == 1
    assert fake_service._shared_chat_client.unsubscribe_calls == 1
