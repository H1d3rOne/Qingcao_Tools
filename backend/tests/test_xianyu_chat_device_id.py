"""Tests for stable chat deviceId derivation.

闲鱼服务端会对 "同 Cookie 但 deviceId 飘" 的请求直接打风控。参考项目
XianYuApis 在 __init__ 时 `generate_device_id(unb)` 生成一次后复用。本测试
锁定当前项目 `_resolve_chat_device_id` 三条关键性质：
1. 只有 `UUID-unb` 形态且后缀匹配当前 unb 的聊天 deviceId 才复用。
2. 扫码/浏览器登录指纹（如 cna）不直接用于 IM login.token。
3. 没有可复用指纹时，同一个 unb 必须在多次调用、多次启动间保持不变。
"""
from __future__ import annotations

import httpx
import pytest

from app.modules.xianyu.service import XianyuService


class _FakeLogin:
    def __init__(self, fingerprint=None):
        self.fingerprint = fingerprint or {}


@pytest.mark.asyncio
async def test_resolve_chat_device_id_ignores_non_chat_fingerprint_even_when_unb_cookie_present(tmp_path):
    service = XianyuService()
    service._chat_device_store_path = tmp_path / "xianyu_chat_devices.json"
    service._auth_login = _FakeLogin(fingerprint={"deviceId": "stable-fp-device"})

    async with httpx.AsyncClient() as client:
        client.cookies.set("unb", "2218827902934", domain=".goofish.com")
        first = service._resolve_chat_device_id(client=client, user_id="")
        second = service._resolve_chat_device_id(client=client, user_id="")

    assert first == second
    assert first != "stable-fp-device"
    assert first.endswith("-2218827902934")


@pytest.mark.asyncio
async def test_resolve_chat_device_id_reuses_valid_fingerprint_for_same_unb(tmp_path):
    service = XianyuService()
    service._chat_device_store_path = tmp_path / "xianyu_chat_devices.json"
    valid_device_id = "12345678-1234-4234-9234-123456789abc-2218827902934"
    service._auth_login = _FakeLogin(fingerprint={"deviceId": valid_device_id})

    async with httpx.AsyncClient() as client:
        client.cookies.set("unb", "2218827902934", domain=".goofish.com")
        resolved = service._resolve_chat_device_id(client=client, user_id="")

    assert resolved == valid_device_id


@pytest.mark.asyncio
async def test_resolve_chat_device_id_is_deterministic_for_same_unb(tmp_path):
    service_a = XianyuService()
    service_a._chat_device_store_path = tmp_path / "xianyu_chat_devices.json"
    service_a._auth_login = _FakeLogin(fingerprint={})
    service_b = XianyuService()
    service_b._chat_device_store_path = tmp_path / "xianyu_chat_devices.json"
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
async def test_resolve_chat_device_id_differs_across_unb(tmp_path):
    service = XianyuService()
    service._chat_device_store_path = tmp_path / "xianyu_chat_devices.json"
    service._auth_login = _FakeLogin(fingerprint={})

    async with httpx.AsyncClient() as client_a, httpx.AsyncClient() as client_b:
        client_a.cookies.set("unb", "1111111111111", domain=".goofish.com")
        client_b.cookies.set("unb", "2222222222222", domain=".goofish.com")

        id_a = service._resolve_chat_device_id(client=client_a, user_id="")
        id_b = service._resolve_chat_device_id(client=client_b, user_id="")

    assert id_a != id_b
