from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from app.modules.xianyu.schemas import XianyuChatProfile
from app.modules.xianyu.service import XianyuService


class DummyClient:
    pass


@asynccontextmanager
async def fake_http_client():
    yield DummyClient()


@pytest.mark.asyncio
async def test_sync_manage_items_page_uses_profile_user_id_and_remote_paging(monkeypatch, tmp_path: Path):
    service = XianyuService()
    service._item_store_path = tmp_path / "items.json"
    service._item_store = None

    captured: dict[str, object] = {}

    monkeypatch.setattr(service, "_get_xianyu_cookie_value", lambda: "cookie")
    monkeypatch.setattr(service, "_create_http_client", lambda cookie: fake_http_client())
    monkeypatch.setattr(service, "_get_cookie_value", lambda client, key: "" if key in {"_m_h5_tk", "unb"} else "")

    async def fake_warmup_token(client):
        return None

    async def fake_refresh_login_state(client):
        return None

    async def fake_get_chat_profile():
        return XianyuChatProfile(
            user_id="fallback-user",
            main_user_id="",
            domain="goofish",
            display_name="卖家",
            avatar="",
        )

    async def fake_execute_api(client, *, api_name, api_url, payload, **kwargs):
        captured["payload"] = payload
        return {
            "data": {
                "cardList": [
                    {
                        "cardData": {
                            "id": "1001",
                            "title": "测试商品",
                            "priceInfo": {"price": "88"},
                            "itemStatus": "onsale",
                        }
                    }
                ],
                "nextPage": True,
                "totalCount": "25",
            }
        }

    monkeypatch.setattr(service, "_warmup_token", fake_warmup_token)
    monkeypatch.setattr(service, "_refresh_login_state", fake_refresh_login_state)
    monkeypatch.setattr(service, "get_chat_profile", fake_get_chat_profile)
    monkeypatch.setattr(service, "_execute_api", fake_execute_api)

    page = await service.sync_manage_items_page(page=1, page_size=20)

    assert captured["payload"]["userId"] == "fallback-user"
    assert page.total == 25
    assert page.has_more is True
    assert [item.item_id for item in page.items] == ["1001"]


@pytest.mark.asyncio
async def test_sync_manage_items_all_counts_unique_items_across_pages(monkeypatch, tmp_path: Path):
    service = XianyuService()
    service._item_store_path = tmp_path / "items.json"
    service._item_store = None

    monkeypatch.setattr(service, "_get_xianyu_cookie_value", lambda: "cookie")
    monkeypatch.setattr(service, "_create_http_client", lambda cookie: fake_http_client())
    monkeypatch.setattr(service, "_get_cookie_value", lambda client, key: "token_x" if key == "_m_h5_tk" else "user-1")

    async def fake_refresh_login_state(client):
        return None

    responses = {
        1: {
            "data": {
                "cardList": [
                    {"cardData": {"id": "1001", "title": "商品1", "priceInfo": {"price": "10"}}},
                    {"cardData": {"id": "1002", "title": "商品2", "priceInfo": {"price": "20"}}},
                ],
                "nextPage": True,
                "totalCount": "3",
            }
        },
        2: {
            "data": {
                "cardList": [
                    {"cardData": {"id": "1002", "title": "商品2新", "priceInfo": {"price": "20"}}},
                    {"cardData": {"id": "1003", "title": "商品3", "priceInfo": {"price": "30"}}},
                ],
                "nextPage": False,
                "totalCount": "3",
            }
        },
    }

    async def fake_execute_api(client, *, payload, **kwargs):
        return responses[payload["pageNumber"]]

    monkeypatch.setattr(service, "_refresh_login_state", fake_refresh_login_state)
    monkeypatch.setattr(service, "_execute_api", fake_execute_api)

    result = await service.sync_manage_items_all()

    assert result == {"synced": 3, "pages": 2}
    stored = service.item_store.list_items(page=1, page_size=10)
    assert [item.item_id for item in stored.items] == ["1001", "1002", "1003"]
