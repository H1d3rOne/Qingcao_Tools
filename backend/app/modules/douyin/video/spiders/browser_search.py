"""
抖音搜索浏览器执行器。

搜索接口当前仅靠本地 bdms VM 生成 a_bogus 仍会触发 BDTuring 空响应；
真实页面里的 bdms/webmssdk 会在 fetch/XHR hook 中结合页面运行态自动签名。
这里复用本地受控浏览器页面完成同源 fetch，让真实 SDK 生成动态 a_bogus，
不需要用户复制浏览器里的 a_bogus。
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from typing import Any

from loguru import logger


class DouyinBrowserSearchExecutor:
    """复用一个 headless 浏览器上下文执行抖音搜索 fetch。"""

    BASE_URL = "https://www.douyin.com"

    def __init__(self):
        self._lock = asyncio.Lock()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._profile_key = ""

    @staticmethod
    def _chrome_executable() -> str | None:
        env_path = os.getenv("DOUYIN_BROWSER_EXECUTABLE")
        if env_path and Path(env_path).exists():
            return env_path

        # macOS 常见路径；其它平台交给 Playwright 使用已安装/下载的 chromium。
        mac_chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if mac_chrome.exists():
            return str(mac_chrome)
        return None

    @staticmethod
    def _to_int(value: Any, fallback: int) -> int:
        try:
            return int(float(value))
        except Exception:
            return fallback

    @staticmethod
    def _profile_fingerprint(auth, profile: dict) -> str:
        raw = "|".join([
            getattr(auth, "cookie_str", "") or "",
            profile.get("user_agent", ""),
            str(profile.get("screen_width", "")),
            str(profile.get("screen_height", "")),
            str(profile.get("browser_language", "")),
        ])
        return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def _same_search_context(current_url: str, refer: str) -> bool:
        """判断当前页面是否仍是同一个搜索上下文，忽略每次生成的 aid。"""
        try:
            current = urlparse(current_url or "")
            target = urlparse(refer or "")
            if current.scheme != target.scheme or current.netloc != target.netloc:
                return False
            if unquote(current.path or "") != unquote(target.path or ""):
                return False
            current_type = (parse_qs(current.query).get("type") or [""])[0]
            target_type = (parse_qs(target.query).get("type") or [""])[0]
            return current_type == target_type
        except Exception:
            return False

    @staticmethod
    def _cookie_items(auth) -> list[dict]:
        items: list[dict] = []
        for name, value in (getattr(auth, "cookie", None) or {}).items():
            if not name or name == "douyin.com":
                continue
            items.append({
                "name": str(name),
                "value": str(value),
                "domain": ".douyin.com",
                "path": "/",
            })
        return items

    async def _reset_context(self):
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        self._context = None
        self._page = None
        self._profile_key = ""

    async def _ensure_page(self, auth, profile: dict):
        try:
            from playwright.async_api import async_playwright
        except Exception as exc:
            raise RuntimeError("抖音搜索需要 Playwright 浏览器执行器，请先安装 backend 依赖 playwright") from exc

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        if self._browser is None or not self._browser.is_connected():
            launch_kwargs = {
                "headless": os.getenv("DOUYIN_BROWSER_HEADLESS", "1") != "0",
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            }
            executable = self._chrome_executable()
            if executable:
                launch_kwargs["executable_path"] = executable
            self._browser = await self._playwright.chromium.launch(**launch_kwargs)

        profile_key = self._profile_fingerprint(auth, profile)
        if self._context is None or self._profile_key != profile_key:
            await self._reset_context()
            width = self._to_int(profile.get("screen_width"), 1920)
            height = self._to_int(profile.get("screen_height"), 1080)
            self._context = await self._browser.new_context(
                user_agent=profile.get("user_agent") or None,
                locale=profile.get("browser_language") or "zh-CN",
                viewport={"width": width, "height": height},
                device_scale_factor=float(profile.get("device_pixel_ratio") or 1),
            )
            cookies = self._cookie_items(auth)
            if cookies:
                await self._context.add_cookies(cookies)
            self._page = await self._context.new_page()
            self._profile_key = profile_key

        return self._page

    async def fetch_text(self, url: str, refer: str, auth, profile: dict, timeout_ms: int = 60_000) -> dict:
        """在真实抖音页面上下文中 fetch URL，让页面 SDK 自动补 a_bogus。"""
        async with self._lock:
            page = await self._ensure_page(auth, profile)
            try:
                current_url = page.url or ""
                if not self._same_search_context(current_url, refer):
                    await page.goto(refer, wait_until="domcontentloaded", timeout=timeout_ms)

                await page.wait_for_function(
                    "() => !!window.bdms || !!window.byted_acrawler",
                    timeout=15_000,
                )
                result = await page.evaluate(
                    """async ({ targetUrl, refer }) => {
                        const res = await fetch(targetUrl, {
                            credentials: 'include',
                            referrer: refer,
                        });
                        const text = await res.text();
                        return {
                            status: res.status,
                            contentType: res.headers.get('content-type') || '',
                            bdturing: res.headers.get('x-vc-bdturing-parameters') || '',
                            msToken: res.headers.get('x-ms-token') || '',
                            webid: res.headers.get('cookie_ttwidinfo_webid') || '',
                            text,
                            href: location.href,
                        };
                    }""",
                    {"targetUrl": url, "refer": refer},
                )
                return result
            except Exception:
                # 页面状态可能被风控脚本污染，下一次重建上下文。
                logger.exception("抖音浏览器搜索 fetch 失败，重置浏览器上下文")
                await self._reset_context()
                raise

    async def close(self):
        await self._reset_context()
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        self._playwright = None


_browser_search_executor = DouyinBrowserSearchExecutor()


def get_browser_search_executor() -> DouyinBrowserSearchExecutor:
    return _browser_search_executor
