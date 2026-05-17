from fastapi.testclient import TestClient

from app.api.deps import get_xianyu_service
from app.main import app


class FakeXianyuService:
    async def get_auth_status(self):
        return {"success": True, "message": "", "is_logged_in": True, "user_info": {"display_name": "测试鱼"}}

    def get_login_qrcode(self):
        return {
            "success": True,
            "message": "二维码已生成",
            "qrcode_url": "https://example.com/qr",
            "qrcode_token": "qr-token",
            "qrcode_image": "data:image/svg+xml;base64,test",
        }

    def check_login_status(self, qrcode_token: str):
        assert qrcode_token == "qr-token"
        return {
            "success": True,
            "message": "登录成功",
            "is_logged_in": True,
            "login_token": "cna=test; cookie2=abc",
        }

    def login(self, method: str = "cookie", cookies: str | None = None):
        assert method == "cookie"
        assert cookies == "cna=test; cookie2=abc"
        return {
            "success": True,
            "message": "Cookie 登录成功",
            "cookies": cookies,
        }

    def logout(self):
        return {"success": True, "message": "已退出登录"}


class FakeExpiredCookieXianyuService(FakeXianyuService):
    async def get_auth_status(self):
        return {"success": True, "message": "", "is_logged_in": False, "user_info": None}


def test_xianyu_auth_endpoints_roundtrip():
    fake_service = FakeXianyuService()
    app.dependency_overrides[get_xianyu_service] = lambda: fake_service

    client = TestClient(app)

    qrcode_resp = client.get("/api/v1/xianyu/auth/qrcode")
    assert qrcode_resp.status_code == 200
    assert qrcode_resp.json()["qrcode_token"] == "qr-token"

    check_resp = client.post("/api/v1/xianyu/auth/check-login", json={"qrcode_token": "qr-token"})
    assert check_resp.status_code == 200
    assert check_resp.json()["is_logged_in"] is True

    login_resp = client.post(
        "/api/v1/xianyu/auth/login",
        json={"method": "cookie", "cookies": "cna=test; cookie2=abc"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["success"] is True

    status_resp = client.get("/api/v1/xianyu/auth/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["is_logged_in"] is True

    logout_resp = client.post("/api/v1/xianyu/auth/logout")
    assert logout_resp.status_code == 200
    assert logout_resp.json()["success"] is True

    app.dependency_overrides.clear()


def test_xianyu_cookie_login_endpoint_rejects_invalid_cookie_after_status_check():
    fake_service = FakeExpiredCookieXianyuService()
    app.dependency_overrides[get_xianyu_service] = lambda: fake_service

    client = TestClient(app)

    login_resp = client.post(
        "/api/v1/xianyu/auth/login",
        json={"method": "cookie", "cookies": "cna=test; cookie2=abc"},
    )

    assert login_resp.status_code == 200
    assert login_resp.json()["success"] is False
    assert "Cookie" in login_resp.json()["message"]

    app.dependency_overrides.clear()



def test_xianyu_auth_status_returns_logged_out_when_profile_fetch_fails(monkeypatch):
    from app.modules.xianyu.service import XianyuService

    service = XianyuService()
    monkeypatch.setattr(service, '_get_xianyu_cookie_value', lambda: 'cna=test; cookie2=abc')

    async def fake_get_user_profile():
        raise ValueError('cookie expired')

    monkeypatch.setattr(service, 'get_user_profile', fake_get_user_profile)

    import asyncio
    result = asyncio.run(service.get_auth_status())

    assert result['success'] is True
    assert result['is_logged_in'] is False
    assert result['user_info'] is None
