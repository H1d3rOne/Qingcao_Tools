"""Tests for stable chat deviceId derivation.

闲鱼服务端会对 "同 Cookie 但 deviceId 飘" 的请求直接打风控。参考项目
XianYuApis 在 __init__ 时 `generate_device_id(unb)` 生成一次后复用。本测试
锁定当前项目 `_resolve_chat_device_id` 两条关键性质：
1. 指纹文件里有 deviceId 时，优先取，绝不生成随机值。
2. 没有指纹只有 unb 时，同一个 unb 必须在多次调用、多次启动间保持不变。
"""
from __future__ import annotations

import httpx
import pytest

from app.modules.xianyu.service import XianyuService


class _FakeLogin:
    def __init__(self, fingerprint=None):
        self.fingerprint = fingerprint or {}


@pytest.mark.asyncio
async def test_resolve_chat_device_id_prefers_fingerprint_even_when_unb_cookie_present():
    service = XianyuService()
    service._auth_login = _FakeLogin(fingerprint={"deviceId": "stable-fp-device"})

    async with httpx.AsyncClient() as client:
        client.cookies.set("unb", "2218827902934", domain=".goofish.com")
        first = service._resolve_chat_device_id(client=client, user_id="")
        second = service._resolve_chat_device_id(client=client, user_id="")

    assert first == "stable-fp-device"
    assert second == "stable-fp-device"


@pytest.mark.asyncio
async def test_resolve_chat_device_id_is_deterministic_for_same_unb():
    service_a = XianyuService()
    service_a._auth_login = _FakeLogin(fingerprint={})
    service_b = XianyuService()
    service_b._auth_login = _FakeLogin(fingerprint={})

    async with httpx.AsyncClient() as client_a, httpx.AsyncClient() as client_b:
        client_a.cookies.set("unb", "2218827902934", domain=".goofish.com")
        client_b.cookies.set("unb", "2218827902934", domain=".goofish.com")

        id_a1 = service_a._resolve_chat_device_id(client=client_a, user_id="")
        id_a2 = service_a._resolve_chat_device_id(client=client_a, user_id="")
        id_b = service_b._resolve_chat_device_id(client=client_b, user_id="")

    assert id_a1 == id_a2 == id_b, "same unb must produce identical deviceId"
    assert id_a1.endswith("-2218827902934")
    # 36-char UUID body + "-" + unb
    assert len(id_a1.split("-2218827902934")[0]) == 36


@pytest.mark.asyncio
async def test_resolve_chat_device_id_differs_across_unb():
    service = XianyuService()
    service._auth_login = _FakeLogin(fingerprint={})

    async with httpx.AsyncClient() as client_a, httpx.AsyncClient() as client_b:
        client_a.cookies.set("unb", "1111111111111", domain=".goofish.com")
        client_b.cookies.set("unb", "2222222222222", domain=".goofish.com")

        id_a = service._resolve_chat_device_id(client=client_a, user_id="")
        id_b = service._resolve_chat_device_id(client=client_b, user_id="")

    assert id_a != id_b
