from fastapi.testclient import TestClient

from app.api.deps import get_xianyu_service
from app.main import app


class FakeXianyuBrowserLoginService:
    async def start_browser_login(self):
        return {
            'success': True,
            'message': '二维码已生成，请使用闲鱼 APP 扫码',
            'session_id': 'session-1',
            'qrcode_image': 'data:image/png;base64,qr',
            'expires_in': 300,
        }

    async def get_browser_login_status(self, session_id: str):
        assert session_id == 'session-1'
        return {
            'success': True,
            'message': '登录成功',
            'status': 'success',
            'is_logged_in': True,
            'login_token': 'cna=test; cookie2=abc',
        }

    async def cancel_browser_login(self, session_id: str):
        assert session_id == 'session-1'
        return {'success': True, 'message': '已取消扫码登录'}


def test_xianyu_browser_login_endpoints_roundtrip():
    app.dependency_overrides[get_xianyu_service] = lambda: FakeXianyuBrowserLoginService()
    client = TestClient(app)

    start_resp = client.post('/api/v1/xianyu/auth/browser-qrcode/start')
    assert start_resp.status_code == 200
    assert start_resp.json()['session_id'] == 'session-1'

    status_resp = client.get('/api/v1/xianyu/auth/browser-qrcode/status', params={'session_id': 'session-1'})
    assert status_resp.status_code == 200
    assert status_resp.json()['status'] == 'success'
    assert status_resp.json()['is_logged_in'] is True

    cancel_resp = client.post('/api/v1/xianyu/auth/browser-qrcode/cancel', json={'session_id': 'session-1'})
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()['success'] is True

    app.dependency_overrides.clear()
