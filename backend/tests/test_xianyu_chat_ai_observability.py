import pytest

from app.modules.xianyu.schemas import XianyuChatAiConfig, XianyuChatAiProvider, XianyuChatProfile
from app.modules.xianyu.service import XianyuService


class _DummyLogger:
    def __init__(self):
        self.info_calls = []
        self.warning_calls = []

    def info(self, msg, *args):
        self.info_calls.append(msg % args if args else msg)

    def warning(self, msg, *args):
        self.warning_calls.append(msg % args if args else msg)


@pytest.mark.asyncio
async def test_auto_reply_logs_skip_reason_when_session_disabled(monkeypatch):
    service = XianyuService()
    service._log = _DummyLogger()
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
    monkeypatch.setattr(service.chat_ai_store, 'get_session_enabled', lambda cid: False)

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

    assert reply is None
    assert any('AI 自动回复跳过：当前会话未开启' in item for item in service._log.info_calls)
