import pytest

from app.modules.xianyu.service import XianyuService


class FakeReusableChatClient:
    def __init__(self, name: str):
        self.name = name
        self.connected = True
        self.close_calls = 0

    def is_connected(self) -> bool:
        return self.connected

    async def close(self):
        self.close_calls += 1
        self.connected = False


@pytest.mark.asyncio
async def test_open_chat_ws_client_reuses_existing_shared_connection(monkeypatch):
    service = XianyuService()
    created: list[FakeReusableChatClient] = []

    async def fake_create_connected_chat_ws_client():
        client = FakeReusableChatClient(f'client-{len(created) + 1}')
        created.append(client)
        return client

    monkeypatch.setattr(service, '_create_connected_chat_ws_client', fake_create_connected_chat_ws_client)

    first = await service.open_chat_ws_client()
    second = await service.open_chat_ws_client()

    assert first is second
    assert len(created) == 1

    first.connected = False
    third = await service.open_chat_ws_client()

    assert third is not first
    assert len(created) == 2
    assert first.close_calls == 1
