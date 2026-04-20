import asyncio
from fastapi.testclient import TestClient

from app.main import app
from app.modules.xianyu.schemas import XianyuChatProfile


class FakeChatClient:
    def __init__(self):
        self.profile = XianyuChatProfile(user_id='111', main_user_id='111', domain='goofish', display_name='卖家', avatar='')
        self._queue = asyncio.Queue()
        self._queue.put_nowait({'lwp': '/s/sync', 'headers': {}, 'body': {'syncPushPackage': {'data': []}}})

    async def next_push(self):
        return await self._queue.get()

    async def close(self):
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

    client = TestClient(app)
    with client.websocket_connect('/api/v1/xianyu/chat/ws') as websocket:
        connected = websocket.receive_json()
        pushed = websocket.receive_json()
        websocket.send_json({'action': 'close'})
        assert connected['type'] == 'connected'
        assert pushed['type'] == 'push'

    assert fake_service.ai_called == 1
