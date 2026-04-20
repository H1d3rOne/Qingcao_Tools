import httpx
import pytest

from app.modules.xianyu.schemas import XianyuChatAiConfig
from app.modules.xianyu.service import XianyuService


@pytest.mark.asyncio
async def test_request_chat_ai_reply_posts_chat_completions(monkeypatch):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured['url'] = str(request.url)
        captured['auth'] = request.headers.get('Authorization')
        captured['payload'] = (await request.aread()).decode()
        return httpx.Response(
            200,
            json={
                'choices': [
                    {
                        'message': {
                            'content': '在的，还可以拍。'
                        }
                    }
                ]
            },
        )

    service = XianyuService()
    config = XianyuChatAiConfig(
        enabled=True,
        base_url='https://example.com/v1',
        model='gpt-4.1-mini',
        system_prompt='reply briefly',
        temperature=0.3,
        api_key_configured=True,
        api_key_masked='sk-****5678',
    )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(service, '_load_secret_chat_ai_api_key', lambda: 'sk-test-12345678')

    reply = await service._request_chat_ai_reply(
        config=config,
        messages=[{'role': 'user', 'content': '这个还在吗？'}],
        transport=transport,
    )

    assert reply == '在的，还可以拍。'
    assert captured['url'] == 'https://example.com/v1/chat/completions'
    assert captured['auth'] == 'Bearer sk-test-12345678'
    assert '这个还在吗？' in captured['payload']


@pytest.mark.asyncio
async def test_request_chat_ai_reply_raises_when_choices_are_missing(monkeypatch):
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'choices': []})

    service = XianyuService()
    config = XianyuChatAiConfig(
        enabled=True,
        base_url='https://example.com/v1',
        model='gpt-4.1-mini',
        system_prompt='reply briefly',
        temperature=0.3,
        api_key_configured=True,
        api_key_masked='sk-****5678',
    )
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(service, '_load_secret_chat_ai_api_key', lambda: 'sk-test-12345678')

    with pytest.raises(ValueError, match='AI 接口未返回可用回复'):
        await service._request_chat_ai_reply(config=config, messages=[{'role': 'user', 'content': 'hi'}], transport=transport)
