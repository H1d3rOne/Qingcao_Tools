from urllib.parse import parse_qs, urlparse

import pytest

from app.modules.douyin.common.auth import DouyinAuth
from app.modules.douyin.live.spiders import live as live_module
from app.modules.douyin.live.spiders.live import DouyinLiveSpider


def make_auth(cookie: str = "ttwid=ttwid-value; msToken=ms-token; s_v_web_id=verify-test") -> DouyinAuth:
    auth = DouyinAuth()
    auth.prepare_auth(cookie)
    return auth


def test_live_page_parser_extracts_user_unique_id_and_room_id():
    spider = DouyinLiveSpider("https://live.douyin.com/123456", make_auth())
    html = r'''
    <script nonce="abc">
      window.__LIVE_DATA__ = "{\"roomId\":\"7317661077232560922\",\"user_unique_id\":\"9876543210123456789\",\"anchor\":{\"id_str\":\"456789\",\"sec_uid\":\"MS4wLjABAAAA\"},\"roomInfo\":{\"room\":{\"status\":2,\"title\":\"测试直播间\"}}}";
    </script>
    '''

    info = spider._parse_live_page_html(html)

    assert info["room_id"] == "7317661077232560922"
    assert info["user_unique_id"] == "9876543210123456789"
    assert info["user_id"] == "9876543210123456789"
    assert info["anchor_id"] == "456789"
    assert info["sec_uid"] == "MS4wLjABAAAA"
    assert info["status"] == "2"


def test_start_ws_uses_page_user_id_prefetch_cursor_and_full_cookie(monkeypatch):
    auth = make_auth()
    spider = DouyinLiveSpider("https://live.douyin.com/123456", auth)
    captured = {}

    monkeypatch.setattr(DouyinLiveSpider, "_ping", lambda self, ws: None)
    monkeypatch.setattr(
        DouyinLiveSpider,
        "_get_webcast_initial_response",
        lambda self, room_id, user_id, web_rid: {"cursor": "cursor-1", "internal_ext": "internal-ext-1"},
    )
    monkeypatch.setattr(
        live_module,
        "generate_signature",
        lambda room_id, user_id: f"sig-{room_id}-{user_id}",
    )

    class FakeWebSocketApp:
        def __init__(self, *, url, header, cookie, on_message, on_error, on_close, on_open):
            captured["url"] = url
            captured["header"] = header
            captured["cookie"] = cookie
            self.on_open = on_open

        def run_forever(self, origin=None):
            captured["origin"] = origin
            self.on_open(self)

        def send(self, *args, **kwargs):
            pass

        def close(self):
            pass

    monkeypatch.setattr(live_module, "WebSocketApp", FakeWebSocketApp)

    try:
        spider.start_ws({
            "room_id": "7317661077232560922",
            "web_rid": "123456",
            "user_unique_id": "9876543210123456789",
            "ttwid": "ttwid-value",
        })
    finally:
        spider.stop()

    parsed = urlparse(captured["url"])
    query = parse_qs(parsed.query)

    assert parsed.netloc == "webcast100-ws-web-hl.douyin.com"
    assert query["user_unique_id"] == ["9876543210123456789"]
    assert query["cursor"] == ["cursor-1"]
    assert query["internal_ext"] == ["internal-ext-1"]
    assert query["signature"] == ["sig-7317661077232560922-9876543210123456789"]
    assert "ttwid=ttwid-value" in captured["cookie"]
    assert "msToken=ms-token" in captured["cookie"]
    assert captured["origin"] == "https://live.douyin.com"


def test_start_ws_reports_missing_user_unique_id_before_signing(monkeypatch):
    auth = make_auth()
    spider = DouyinLiveSpider("https://live.douyin.com/123456", auth)
    messages = []
    spider.set_message_callback(messages.append)

    monkeypatch.setattr(
        live_module,
        "generate_signature",
        lambda *args, **kwargs: pytest.fail("缺少 user_unique_id 时不应生成弹幕签名"),
    )
    monkeypatch.setattr(
        live_module,
        "WebSocketApp",
        lambda *args, **kwargs: pytest.fail("缺少 user_unique_id 时不应创建 WebSocket"),
    )

    spider.start_ws({
        "room_id": "7317661077232560922",
        "web_rid": "123456",
        "ttwid": "ttwid-value",
    })

    assert messages == [{
        "type": "error",
        "message": "无法获取 user_unique_id，无法建立弹幕连接；请更新抖音直播 Cookie 后重试",
    }]
