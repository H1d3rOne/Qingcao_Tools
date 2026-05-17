import asyncio

from app.modules.xianyu.schemas import XianyuChatConversation, XianyuChatConversationPage
from app.modules.xianyu.service import XianyuService


def test_open_chat_session_prefers_existing_conversation(monkeypatch):
    service = XianyuService()

    existing = XianyuChatConversation(
        cid='cid-1',
        session_id='cid-1',
        session_type=1,
        biz_type='1',
        title='卖家会话',
        peer_user_id='2218736549452',
        peer_display_name='卖家',
        peer_avatar='',
        item_id='101',
        item_title='测试商品',
        item_image='',
        last_message_id='',
        last_message_summary='',
        last_message_time=0,
        last_message_time_text='',
        unread_count=0,
        red_point=0,
        top_rank=0,
        muted=False,
        visible=True,
        can_send=True,
    )

    async def fake_list_chat_conversations(offset=0, limit=20):
        return XianyuChatConversationPage(total=1, offset=0, limit=40, conversations=[existing])

    monkeypatch.setattr(service, 'list_chat_conversations', fake_list_chat_conversations)

    result = asyncio.run(service.open_chat_session(item_id='101', peer_user_id='2218736549452'))

    assert result['success'] is True
    assert result['cid'] == 'cid-1'
    assert result['session'].peer_user_id == '2218736549452'


def test_open_chat_session_returns_failure_when_creation_unavailable(monkeypatch):
    service = XianyuService()

    async def fake_list_chat_conversations(offset=0, limit=20):
        return XianyuChatConversationPage(total=0, offset=0, limit=40, conversations=[])

    async def fake_open_chat_session_via_bootstrap(item_id: str, peer_user_id: str):
        return {'success': False, 'message': '创建会话失败'}

    monkeypatch.setattr(service, 'list_chat_conversations', fake_list_chat_conversations)
    monkeypatch.setattr(service, '_open_chat_session_via_bootstrap', fake_open_chat_session_via_bootstrap)

    result = asyncio.run(service.open_chat_session(item_id='101', peer_user_id='222'))

    assert result == {'success': False, 'message': '创建会话失败'}
