import asyncio

import pytest

from app.modules.xianyu.schemas import XianyuChatAiConfig, XianyuChatAiProvider, XianyuChatProfile
from app.modules.xianyu.service import XianyuService


class FakeBroadcastChatClient:
    def __init__(self):
        self.profile = XianyuChatProfile(
            user_id='111',
            main_user_id='111',
            domain='goofish',
            display_name='卖家',
            avatar='',
        )
        self.connected = True
        self.subscribers: list[asyncio.Queue] = []

    def is_connected(self) -> bool:
        return self.connected

    def subscribe_pushes(self):
        queue = asyncio.Queue()
        self.subscribers.append(queue)
        return queue

    def unsubscribe_pushes(self, queue):
        if queue in self.subscribers:
            self.subscribers.remove(queue)

    async def emit(self, payload):
        for queue in list(self.subscribers):
            await queue.put(payload)

    async def close(self):
        self.connected = False


@pytest.mark.asyncio
async def test_chat_ai_background_listener_replies_without_frontend_ws(monkeypatch):
    service = XianyuService()
    fake_client = FakeBroadcastChatClient()

    provider = XianyuChatAiProvider(
        id='provider-1',
        name='demo',
        base_url='https://example.com/v1',
        model='gpt-4.1-mini',
        system_prompt='reply briefly',
        api_key_configured=True,
        api_key_masked='sk-****5678',
        is_active=True,
    )

    monkeypatch.setattr(service, 'open_chat_ws_client', lambda: asyncio.sleep(0, result=fake_client))
    monkeypatch.setattr(
        service,
        'get_chat_ai_config',
        lambda: XianyuChatAiConfig(enabled=True, providers=[provider], active_provider_id=provider.id),
    )
    monkeypatch.setattr(service.chat_ai_store, 'get_active_provider', lambda: provider)
    monkeypatch.setattr(service.chat_ai_store, 'has_any_enabled_session', lambda: True)
    monkeypatch.setattr(service.chat_ai_store, 'get_session_enabled', lambda cid: cid == 'cid-1@goofish')
    monkeypatch.setattr(service, '_get_xianyu_cookie_value', lambda: 'cookie')

    sent = {}

    async def fake_request_chat_ai_reply(**kwargs):
        return '在的，现在还在。'

    async def fake_send_chat_text(cid: str, text: str):
        sent['cid'] = cid
        sent['text'] = text
        return None

    monkeypatch.setattr(service, '_request_chat_ai_reply', fake_request_chat_ai_reply)
    monkeypatch.setattr(service, 'send_chat_text', fake_send_chat_text)

    await service.ensure_chat_ai_listener()
    for _ in range(20):
        if fake_client.subscribers:
            break
        await asyncio.sleep(0.01)

    monkeypatch.setattr(
        service,
        'decode_chat_push',
        lambda payload: {
            'type': 'sync',
            'items': [
                {
                    'biz_type': 40000,
                    'decoded': {
                        'raw_text': 'same-message',
                        'json_objects': [
                            {
                                '1': {
                                    '2': 'cid-1@goofish',
                                    '10': {
                                        'senderUserId': '222',
                                        'reminderContent': '这个还在吗？',
                                        'reminderTitle': '买家A',
                                    },
                                }
                            }
                        ],
                    },
                }
            ],
        },
    )

    try:
        await fake_client.emit({'lwp': '/s/sync', 'body': {'syncPushPackage': {'data': []}}})
        await asyncio.sleep(0.1)

        assert sent == {'cid': 'cid-1@goofish', 'text': '在的，现在还在。'}
    finally:
        await service.stop_chat_ai_listener()
