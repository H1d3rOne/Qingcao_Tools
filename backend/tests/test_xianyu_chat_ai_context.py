import pytest

from app.modules.xianyu.schemas import (
    XianyuChatAiConfig,
    XianyuChatAiProvider,
    XianyuChatMessage,
    XianyuChatMessagePage,
    XianyuChatProfile,
)
from app.modules.xianyu.service import XianyuService


def test_extract_ai_candidate_includes_sender_name():
    service = XianyuService()

    candidate = service._extract_ai_candidate(
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
    )

    assert candidate is not None
    assert candidate['sender_name'] == '买家A'


@pytest.mark.asyncio
async def test_auto_reply_system_prompt_includes_sender_name(monkeypatch):
    service = XianyuService()
    profile = XianyuChatProfile(user_id='111', main_user_id='111', domain='goofish', display_name='卖家', avatar='')

    provider = XianyuChatAiProvider(
        id='provider-1',
        name='demo',
        base_url='https://example.com/v1',
        active_model='gpt-4.1-mini',
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
        return None

    async def fake_get_item_title(cid: str):
        return ''

    monkeypatch.setattr(service, '_request_chat_ai_reply', fake_request_chat_ai_reply)
    monkeypatch.setattr(service, 'send_chat_text', fake_send_chat_text)
    monkeypatch.setattr(service, '_get_conversation_item_title', fake_get_item_title)

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
    system_prompt = sent['messages'][0]['content']
    assert '买家A' in system_prompt
    last_msg = sent['messages'][-1]
    assert last_msg['role'] == 'user'
    assert last_msg['content'] == '这个还在吗？'


@pytest.mark.asyncio
async def test_auto_reply_includes_multiturn_history_and_item_title(monkeypatch):
    service = XianyuService()
    profile = XianyuChatProfile(user_id='111', main_user_id='111', domain='goofish', display_name='卖家', avatar='')

    provider = XianyuChatAiProvider(
        id='provider-1',
        name='demo',
        base_url='https://example.com/v1',
        active_model='gpt-4.1-mini',
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

    async def fake_list_chat_messages(cid: str, cursor=None, limit=20, direction='prev'):
        return XianyuChatMessagePage(
            cid=cid,
            cursor=None,
            has_more=False,
            messages=[
                XianyuChatMessage(
                    cid=cid,
                    message_id='m1',
                    numeric_message_id=1,
                    sender_uid='111',
                    sender_display_name='卖家',
                    direction='out',
                    content_type=1,
                    summary='你好，在的',
                    text='你好，在的',
                    image_url='',
                    create_at=1,
                    create_at_text='',
                    read_status=1,
                    raw_extension={},
                ),
                XianyuChatMessage(
                    cid=cid,
                    message_id='m2',
                    numeric_message_id=2,
                    sender_uid='222',
                    sender_display_name='买家A',
                    direction='in',
                    content_type=1,
                    summary='包邮吗',
                    text='包邮吗',
                    image_url='',
                    create_at=2,
                    create_at_text='',
                    read_status=1,
                    raw_extension={},
                ),
            ],
        )

    sent = {}

    async def fake_request_chat_ai_reply(**kwargs):
        sent['messages'] = kwargs['messages']
        return '可以包邮。'

    async def fake_send_chat_text(cid: str, text: str):
        return None

    async def fake_get_item_title(cid: str):
        return 'iPhone 15 Pro Max 256G 国行'

    monkeypatch.setattr(service, 'list_chat_messages', fake_list_chat_messages)
    monkeypatch.setattr(service, '_request_chat_ai_reply', fake_request_chat_ai_reply)
    monkeypatch.setattr(service, 'send_chat_text', fake_send_chat_text)
    monkeypatch.setattr(service, '_get_conversation_item_title', fake_get_item_title)

    decoded = {
        'type': 'sync',
        'items': [
            {
                'biz_type': 40000,
                'decoded': {
                    'raw_text': 'same-message-2',
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

    assert reply == '可以包邮。'
    messages = sent['messages']
    # system prompt includes item title and sender name
    system = messages[0]
    assert system['role'] == 'system'
    assert 'iPhone 15 Pro Max' in system['content']
    assert '买家A' in system['content']
    # multi-turn history: assistant then user
    assert messages[1] == {'role': 'assistant', 'content': '你好，在的'}
    assert messages[2] == {'role': 'user', 'content': '包邮吗'}
    # latest message is last
    assert messages[-1] == {'role': 'user', 'content': '这个还在吗？'}
    assert len(messages) == 4  # system + 2 history + 1 current


@pytest.mark.asyncio
async def test_different_conversations_get_isolated_context(monkeypatch):
    """Two conversations get different system prompts (different item titles)."""
    service = XianyuService()

    provider = XianyuChatAiProvider(
        id='p1',
        name='demo',
        base_url='https://example.com/v1',
        active_model='gpt-4.1-mini',
        system_prompt='你是闲鱼客服',
        api_key_configured=True,
        api_key_masked='sk-****',
        is_active=True,
    )

    msgs_a = service._build_chat_ai_messages(
        provider=provider,
        text='多少钱',
        sender_name='买家甲',
        item_title='iPhone 15',
    )
    msgs_b = service._build_chat_ai_messages(
        provider=provider,
        text='能便宜吗',
        sender_name='买家乙',
        item_title='MacBook Pro M4',
    )

    assert 'iPhone 15' in msgs_a[0]['content']
    assert 'MacBook Pro M4' not in msgs_a[0]['content']
    assert 'MacBook Pro M4' in msgs_b[0]['content']
    assert 'iPhone 15' not in msgs_b[0]['content']
    assert '买家甲' in msgs_a[0]['content']
    assert '买家乙' in msgs_b[0]['content']
