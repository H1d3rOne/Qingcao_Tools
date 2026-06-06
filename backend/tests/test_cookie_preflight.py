import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.v1 import xianyu as xianyu_api
from app.main import app
from app.utils import dy_util


def test_douyin_work_reports_missing_cookie_before_parsing(monkeypatch):
    monkeypatch.setattr(deps.settings.cookies, "douyin", "", raising=False)
    monkeypatch.setattr(
        dy_util,
        "_get_dy_js",
        lambda: pytest.fail("缺少抖音 Cookie 时不应进入 JS 签名逻辑"),
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/douyin/work/info",
        json={"url": "https://v.douyin.com/test/"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"] == deps.DOUYIN_COOKIE_MISSING_MESSAGE


def test_douyin_js_dependency_error_is_user_friendly():
    raw_error = (
        "Error: Cannot find module 'jsrsasign'\n"
        "Require stack:\n"
        "- C:\\Projects\\Qingcao_Tools\\backend\\[stdin]"
    )

    with pytest.raises(RuntimeError) as exc_info:
        dy_util._raise_friendly_js_error(Exception(raw_error))

    assert str(exc_info.value) == "后端 JS 依赖未安装（缺少 jsrsasign），请在 backend 目录执行 npm ci 后重启后端"


def test_douyin_live_signature_does_not_require_sdenv(monkeypatch):
    dy_util._sign_js = None
    captured = {}

    class FakeContext:
        def call(self, function_name, *args):
            assert function_name == "get_signature"
            assert len(args) == 1
            assert len(args[0]) == 32
            return "mock-signature"

    def fake_compile_js(script_path, *module_names, **kwargs):
        captured["module_names"] = module_names
        captured["live_danmu"] = kwargs.get("live_danmu")
        return FakeContext()

    monkeypatch.setattr(dy_util, "_compile_js", fake_compile_js)

    try:
        assert dy_util.generate_signature("room-id", "user-id") == "mock-signature"
        assert captured["module_names"] == ()
        assert captured["live_danmu"] is True
    finally:
        dy_util._sign_js = None


def test_quark_files_routes_require_cookie(monkeypatch):
    monkeypatch.setattr(deps, "load_quark_cookie_string", lambda *args, **kwargs: "")
    monkeypatch.setattr(deps.settings.cookies, "quark", "", raising=False)
    app.dependency_overrides.clear()

    client = TestClient(app)
    response = client.get("/api/v1/quark/files/list")

    assert response.status_code == 400
    assert response.json()["detail"] == deps.QUARK_COOKIE_MISSING_MESSAGE


def test_xianyu_feature_routes_require_cookie(monkeypatch):
    monkeypatch.setattr(deps, "load_xianyu_cookie_string", lambda *args, **kwargs: "")
    monkeypatch.setattr(deps.settings.cookies, "xianyu", "", raising=False)
    app.dependency_overrides.clear()

    client = TestClient(app)
    response = client.get("/api/v1/xianyu/manage/items")

    assert response.status_code == 400
    assert response.json()["detail"] == deps.XIANYU_COOKIE_MISSING_MESSAGE


def test_xianyu_chat_ws_reports_missing_cookie(monkeypatch):
    monkeypatch.setattr(xianyu_api, "is_xianyu_cookie_configured", lambda: False)

    client = TestClient(app)
    with client.websocket_connect("/api/v1/xianyu/chat/ws") as websocket:
        payload = websocket.receive_json()

    assert payload == {
        "type": "error",
        "message": deps.XIANYU_COOKIE_MISSING_MESSAGE,
    }
