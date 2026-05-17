import asyncio

from app.modules.xianyu.schemas import XianyuChatProfile
from app.modules.xianyu.service import XianyuService


class _AsyncClientContext:
    def __init__(self, client):
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_get_chat_session_user_info_uses_idlemessage_user_query_payload(monkeypatch):
    service = XianyuService()
    dummy_client = object()
    captured = {}

    monkeypatch.setattr(service, '_require_xianyu_cookie', lambda: 'cookie')
    monkeypatch.setattr(service, '_create_http_client', lambda cookie: _AsyncClientContext(dummy_client))

    async def fake_execute_api(client, api_name, api_url, payload, extra_params=None):
        captured['client'] = client
        captured['api_name'] = api_name
        captured['api_url'] = api_url
        captured['payload'] = payload
        captured['extra_params'] = extra_params
        return {'data': {'userInfo': {'fishNick': '梦想蛋糕', 'logo': 'http://img.alicdn.com/avatar.jpg'}}}

    monkeypatch.setattr(service, '_execute_api', fake_execute_api)

    result = asyncio.run(service.get_chat_session_user_info('60653115357'))

    assert result == {'userInfo': {'fishNick': '梦想蛋糕', 'logo': 'http://img.alicdn.com/avatar.jpg'}}
    assert captured['client'] is dummy_client
    assert captured['api_name'] == service.chat_user_query_api_name
    assert captured['api_url'] == service.chat_user_query_api_url
    assert captured['payload'] == {
        'type': 0,
        'sessionType': 1,
        'sessionId': '60653115357',
        'isOwner': False,
    }
    assert captured['extra_params'] is None


def test_get_peer_user_info_still_uses_page_head_payload(monkeypatch):
    service = XianyuService()
    dummy_client = object()
    captured = {}

    monkeypatch.setattr(service, '_require_xianyu_cookie', lambda: 'cookie')
    monkeypatch.setattr(service, '_create_http_client', lambda cookie: _AsyncClientContext(dummy_client))

    async def fake_execute_api(client, api_name, api_url, payload, extra_params=None):
        captured['client'] = client
        captured['api_name'] = api_name
        captured['api_url'] = api_url
        captured['payload'] = payload
        captured['extra_params'] = extra_params
        return {'data': {'module': {'base': {'displayName': '梦想蛋糕'}}}}

    monkeypatch.setattr(service, '_execute_api', fake_execute_api)

    result = asyncio.run(service.get_peer_user_info('2221545010258'))

    assert result == {'module': {'base': {'displayName': '梦想蛋糕'}}}
    assert captured['client'] is dummy_client
    assert captured['api_name'] == service.page_head_api_name
    assert captured['api_url'] == service.page_head_api_url
    assert captured['payload'] == {'self': False, 'userId': '2221545010258'}
    assert captured['extra_params'] is None


def test_map_chat_conversation_prefers_chat_user_query_nick_and_logo():
    service = XianyuService()
    profile = XianyuChatProfile(user_id='10001', main_user_id='10001', domain='goofish', display_name='我', avatar='')
    payload = {
        'singleChatUserConversation': {
            'singleChatConversation': {
                'cid': '60653115357@goofish',
                'pairFirst': '10001@goofish',
                'pairSecond': '2221545010258@goofish',
                'bizType': '1',
                'extension': {
                    'itemId': '101',
                    'itemTitle': '测试商品',
                },
            },
            'lastMessage': {
                'message': {
                    'messageId': 'msg-1',
                    'createAt': 1710000000000,
                    'extension': {},
                }
            },
            'visible': 1,
            'redPoint': 0,
            'topRank': 0,
            'muteNotification': False,
        }
    }
    peer_info_cache = {
        '60653115357': {
            'userInfo': {
                'fishNick': '梦想蛋糕',
                'logo': ' http://img.alicdn.com/bao/uploaded/test-avatar.jpg ',
            }
        }
    }

    conversation = service._map_chat_conversation(payload, profile, peer_info_cache)

    assert conversation.peer_user_id == '2221545010258'
    assert conversation.peer_display_name == '梦想蛋糕'
    assert conversation.title == '梦想蛋糕'
    assert conversation.peer_avatar == 'https://img.alicdn.com/bao/uploaded/test-avatar.jpg'
    assert conversation.item_title == '测试商品'
