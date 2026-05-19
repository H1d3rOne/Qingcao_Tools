import pytest

from app.modules.xianyu.schemas import XianyuChatAiConfig, XianyuChatAiProvider, XianyuChatProfile
from app.modules.xianyu.service import XianyuService


@pytest.mark.asyncio
async def test_maybe_auto_reply_from_decoded_push_replies_once_for_enabled_text(monkeypatch):
    service = XianyuService()
    profile = XianyuChatProfile(user_id='111', main_user_id='111', domain='goofish', display_name='卖家', avatar='')

    monkeypatch.setattr(
        service,
        'get_chat_ai_config',
        lambda: XianyuChatAiConfig(
            enabled=True,
            base_url='https://example.com/v1',
            model='gpt-4.1-mini',
            system_prompt='reply briefly',
            temperature=0.3,
            api_key_configured=True,
            api_key_masked='sk-****5678',
        ),
    )
    monkeypatch.setattr(service.chat_ai_store, 'get_session_enabled', lambda cid: cid == 'cid-1')

    sent = {}

    async def fake_request_chat_ai_reply(**kwargs):
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
    }

    reply = await service.maybe_auto_reply_from_decoded_push(profile, decoded)
    duplicate_reply = await service.maybe_auto_reply_from_decoded_push(profile, decoded)

    assert reply == '在的，现在还在。'
    assert duplicate_reply is None
    assert sent == {'cid': 'cid-1', 'text': '在的，现在还在。'}


@pytest.mark.asyncio
async def test_maybe_auto_reply_marks_read_before_requesting_ai(monkeypatch):
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
    order = []

    monkeypatch.setattr(
        service,
        'get_chat_ai_config',
        lambda: XianyuChatAiConfig(enabled=True, providers=[provider], active_provider_id=provider.id),
    )
    monkeypatch.setattr(service.chat_ai_store, 'get_active_provider', lambda: provider)
    monkeypatch.setattr(service.chat_ai_store, 'get_session_enabled', lambda cid: cid == 'cid-1')

    async def fake_mark_chat_read(cid: str):
        order.append(('read', cid))
        return True

    async def fake_request_chat_ai_reply(**kwargs):
        order.append(('ai', kwargs['messages'][-1]['content']))
        return '在的。'

    async def fake_send_chat_text(cid: str, text: str):
        order.append(('send', cid, text))
        return None

    monkeypatch.setattr(service, 'mark_chat_read', fake_mark_chat_read)
    monkeypatch.setattr(service, '_request_chat_ai_reply', fake_request_chat_ai_reply)
    monkeypatch.setattr(service, 'send_chat_text', fake_send_chat_text)

    decoded = {
        'type': 'sync',
        'items': [
            {
                'biz_type': 40000,
                'decoded': {
                    'raw_text': 'msg-read-before-ai',
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
    }

    reply = await service.maybe_auto_reply_from_decoded_push(profile, decoded)

    assert reply == '在的。'
    assert order[:3] == [
        ('read', 'cid-1@goofish'),
        ('ai', '这个还在吗？'),
        ('send', 'cid-1', '在的。'),
    ]


@pytest.mark.asyncio
async def test_maybe_auto_reply_from_decoded_push_skips_when_global_or_session_disabled(monkeypatch):
    service = XianyuService()
    profile = XianyuChatProfile(user_id='111', main_user_id='111', domain='goofish', display_name='卖家', avatar='')

    monkeypatch.setattr(
        service,
        'get_chat_ai_config',
        lambda: XianyuChatAiConfig(
            enabled=False,
            base_url='https://example.com/v1',
            model='gpt-4.1-mini',
            system_prompt='reply briefly',
            temperature=0.3,
            api_key_configured=True,
            api_key_masked='sk-****5678',
        ),
    )

    decoded = {
        'type': 'sync',
        'items': [
            {
                'biz_type': 40000,
                'decoded': {
                    'raw_text': 'msg-2',
                    'json_objects': [
                        {'1': {'2': 'cid-2@goofish', '10': {'senderUserId': '222', 'reminderContent': 'hi'}}}
                    ],
                },
            }
        ],
    }

    assert await service.maybe_auto_reply_from_decoded_push(profile, decoded) is None
