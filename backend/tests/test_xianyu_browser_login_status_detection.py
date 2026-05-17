import asyncio

from app.modules.xianyu.service import XianyuService


class FakeStatusPage:
    def __init__(self, *, url: str, text: str = ""):
        self.url = url
        self._text = text

    async def wait_for_load_state(self, *_args, **_kwargs):
        return None

    async def wait_for_timeout(self, *_args, **_kwargs):
        return None

    async def evaluate(self, _script: str):
        return self._text


class FakeStatusContext:
    def __init__(self, cookies):
        self._cookies = cookies

    async def cookies(self):
        return self._cookies


def test_browser_login_status_detects_success_with_havana_cookie_before_unb():
    service = XianyuService()
    page = FakeStatusPage(
        url="https://passport.goofish.com/mini_login.htm",
        text="手机扫码安全登录",
    )
    context = FakeStatusContext(
        [
            {"name": "cna", "value": "test-cna", "domain": ".goofish.com"},
            {"name": "cookie2", "value": "cookie2-token", "domain": ".goofish.com"},
            {"name": "havana_lgc2_77", "value": "encoded-login-state", "domain": ".goofish.com"},
            {"name": "tracknick", "value": "test-user", "domain": ".goofish.com"},
        ]
    )

    result = asyncio.run(service._browser_login_status_from_page(page, context))

    assert result["status"] == "success"
    assert "havana_lgc2_77=encoded-login-state" in result["cookie_string"]


def test_browser_login_cookie_string_keeps_login_state_cookies():
    service = XianyuService()

    cookie_string = service._browser_login_cookie_string(
        [
            {"name": "cna", "value": "test-cna", "domain": ".goofish.com"},
            {"name": "cookie2", "value": "cookie2-token", "domain": ".goofish.com"},
            {"name": "havana_lgc2_77", "value": "encoded-login-state", "domain": ".goofish.com"},
            {"name": "_m_h5_tk", "value": "h5-token", "domain": ".goofish.com"},
            {"name": "unrelated", "value": "ignore-me", "domain": ".goofish.com"},
        ]
    )

    assert "havana_lgc2_77=encoded-login-state" in cookie_string
    assert "_m_h5_tk=h5-token" in cookie_string
    assert "unrelated=ignore-me" in cookie_string  # goofish 域 cookie 也应保留，避免遗漏关键登录态
