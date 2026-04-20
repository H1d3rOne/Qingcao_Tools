from fastapi.testclient import TestClient

from app.api.deps import get_xianyu_service
from app.main import app


class FakeXianyuAiService:
    def get_chat_ai_config(self):
        return {
            'enabled': True,
            'base_url': 'https://example.com/v1',
            'model': 'gpt-4.1-mini',
            'system_prompt': 'reply briefly',
            'temperature': 0.3,
            'api_key_configured': True,
            'api_key_masked': 'sk-****5678',
        }

    def update_chat_ai_config(self, request):
        return self.get_chat_ai_config()

    def list_chat_ai_session_states(self, cids=None):
        return [{'cid': 'cid-1', 'enabled': True}]

    def set_chat_ai_session_state(self, cid: str, enabled: bool):
        return {'cid': cid, 'enabled': enabled}

    async def test_chat_ai_reply(self, text: str, cid: str = ''):
        return '在的，还可以拍。'


def test_xianyu_chat_ai_routes_roundtrip():
    fake_service = FakeXianyuAiService()
    app.dependency_overrides[get_xianyu_service] = lambda: fake_service
    client = TestClient(app)

    config_resp = client.get('/api/v1/xianyu/chat/ai/config')
    assert config_resp.status_code == 200
    assert config_resp.json()['data']['enabled'] is True

    update_resp = client.post('/api/v1/xianyu/chat/ai/config', json={
        'enabled': True,
        'base_url': 'https://example.com/v1',
        'api_key': '',
        'model': 'gpt-4.1-mini',
        'system_prompt': 'reply briefly',
        'temperature': 0.3,
    })
    assert update_resp.status_code == 200

    sessions_resp = client.get('/api/v1/xianyu/chat/ai/sessions', params=[('cid', 'cid-1')])
    assert sessions_resp.status_code == 200
    assert sessions_resp.json()['data'][0]['cid'] == 'cid-1'

    toggle_resp = client.post('/api/v1/xianyu/chat/ai/sessions/cid-1', json={'enabled': True})
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()['data']['enabled'] is True

    test_resp = client.post('/api/v1/xianyu/chat/ai/test', json={'text': '你好', 'cid': 'cid-1'})
    assert test_resp.status_code == 200
    assert test_resp.json()['data']['reply'] == '在的，还可以拍。'

    app.dependency_overrides.clear()
