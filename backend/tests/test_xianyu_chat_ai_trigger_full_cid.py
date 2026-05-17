import pytest

from app.modules.xianyu.schemas import XianyuChatAiConfig, XianyuChatAiProvider, XianyuChatProfile
from app.modules.xianyu.service import XianyuService


@pytest.mark.asyncio
async def test_maybe_auto_reply_from_decoded_push_uses_full_cid_for_session_enabled(monkeypatch):
    service = XianyuService()
    profile = XianyuChatProfile(user_id='111', main_user_id='111', domain='goofish', display_name='卖家', avatar='')

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
    monkeypatch.setattr(
        service,
        'get_chat_ai_config',
        lambda: XianyuChatAiConfig(enabled=True, providers=[provider], active_provider_id=provider.id),
    )
    monkeypatch.setattr(service.chat_ai_store, 'get_active_provider', lambda: provider)
    monkeypatch.setattr(service.chat_ai_store, 'get_session_enabled', lambda cid: cid == '60613035186@goofish')

    sent = {}

    async def fake_request_chat_ai_reply(**kwargs):
        sent['messages'] = kwargs['messages']
        return '在的，现在还在。'

    async def fake_send_chat_text(cid: str, text: str):
        sent['cid'] = cid
        sent['text'] = text
        return None

    monkeypatch.setattr(service, '_request_chat_ai_reply', fake_request_chat_ai_reply)
    monkeypatch.setattr(service, 'send_chat_text', fake_send_chat_text)

    decoded = {
        'type': 'sync',
        'items': [
            {
                'biz_type': 40000,
                'decoded': {
                    'raw_text': 'same-message',
                    'json_objects': [
                        {
                            '1': {
                                '2': '60613035186@goofish',
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
    }

    reply = await service.maybe_auto_reply_from_decoded_push(profile, decoded)

    assert reply == '在的，现在还在。'
    assert sent['cid'] == '60613035186@goofish'
    # session_enabled mock only returns True for the full cid — a reply proves the full cid was used
    last_msg = sent['messages'][-1]
    assert last_msg == {'role': 'user', 'content': '这个还在吗？'}
