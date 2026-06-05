from fastapi.testclient import TestClient

from app.api import deps
from app.api.v1 import xianyu as xianyu_api
from app.main import app


def test_douyin_work_reports_missing_cookie_before_parsing(monkeypatch):
    monkeypatch.setattr(deps.settings.cookies, "douyin", "", raising=False)

    client = TestClient(app)
    response = client.post(
        "/api/v1/douyin/work/info",
        json={"url": "https://v.douyin.com/test/"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"] == deps.DOUYIN_COOKIE_MISSING_MESSAGE


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
