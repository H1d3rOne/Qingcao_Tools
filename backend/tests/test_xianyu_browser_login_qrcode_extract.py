import asyncio
import base64

from app.modules.xianyu.service import XianyuService


class FakeLocator:
    def __init__(self, *, count: int = 1, src: str = "", screenshot_bytes: bytes = b""):
        self._count = count
        self._src = src
        self._screenshot_bytes = screenshot_bytes
        self.first = self

    async def count(self):
        return self._count

    async def get_attribute(self, name: str):
        if name == "src":
            return self._src
        return None

    async def screenshot(self, type: str = "png"):
        return self._screenshot_bytes


class FakePage:
    def __init__(self):
        self.canvas_locator = FakeLocator(screenshot_bytes=b"canvas-qr-bytes")
        self.full_page_screenshot_called = False

    def locator(self, selector: str):
        if selector == "canvas":
            return self.canvas_locator
        return FakeLocator(count=0)

    async def evaluate(self, script: str, selector: str):
        if selector == "canvas":
            raise RuntimeError("SecurityError: tainted canvas")
        return ""

    async def screenshot(self, type: str = "png", full_page: bool = False):
        self.full_page_screenshot_called = True
        return b"full-page-bytes"


def test_browser_login_qrcode_uses_canvas_screenshot_when_canvas_is_tainted():
    service = XianyuService()
    page = FakePage()

    result = asyncio.run(service._browser_login_qrcode_data_url(page))

    expected = "data:image/png;base64," + base64.b64encode(b"canvas-qr-bytes").decode("utf-8")
    assert result == expected
    assert page.full_page_screenshot_called is False
