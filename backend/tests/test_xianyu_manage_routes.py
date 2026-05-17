from fastapi.testclient import TestClient

from app.api.deps import get_xianyu_service
from app.main import app


class FakeManageService:
    async def ensure_chat_ai_listener(self):
        return True

    def list_manage_items(self, page=1, page_size=20):
        return {
            "items": [
                {
                    "item_id": "1001",
                    "item_title": "Switch",
                    "item_price": "299",
                    "item_image": "",
                    "item_status": "onsale",
                    "item_detail": "detail",
                    "multi_quantity_delivery": False,
                    "synced_at": 1,
                    "updated_at": 1,
                }
            ],
            "total": 1,
            "page": page,
            "page_size": page_size,
            "has_more": False,
        }

    async def sync_manage_items_page(self, page=1, page_size=20):
        return self.list_manage_items(page, page_size)

    async def sync_manage_items_all(self):
        return {"synced": 1, "pages": 1}

    def get_manage_item(self, item_id: str):
        return self.list_manage_items()["items"][0]

    def update_manage_item(self, item_id: str, item_detail: str):
        item = self.list_manage_items()["items"][0]
        item["item_detail"] = item_detail
        return item

    def set_manage_item_multi_quantity_delivery(self, item_id: str, enabled: bool):
        item = self.list_manage_items()["items"][0]
        item["multi_quantity_delivery"] = enabled
        return item

    def list_delivery_rules(self):
        return [
            {
                "id": "rule-1",
                "name": "卡密发货",
                "enabled": True,
                "item_id": "1001",
                "keyword": "",
                "match_mode": "item_id",
                "delivery_text": "卡密：123",
                "send_chat_text": True,
                "send_dummy_ship": True,
                "created_at": 1,
                "updated_at": 1,
            }
        ]

    def create_delivery_rule(self, request):
        return self.list_delivery_rules()[0]

    def update_delivery_rule(self, rule_id, request):
        return self.list_delivery_rules()[0]

    def delete_delivery_rule(self, rule_id):
        return True

    def toggle_delivery_rule(self, rule_id):
        rule = self.list_delivery_rules()[0]
        rule["enabled"] = False
        return rule

    def get_delivery_runtime_status(self):
        return {
            "running": False,
            "last_event_at": 0,
            "last_success_at": 0,
            "last_failure_at": 0,
            "last_error": "",
            "enabled_rule_count": 1,
            "recent_success_count": 0,
            "recent_failure_count": 0,
        }

    def list_delivery_executions(self, limit=20):
        return []


def test_manage_item_routes_roundtrip():
    app.dependency_overrides[get_xianyu_service] = lambda: FakeManageService()
    client = TestClient(app)

    assert client.get("/api/v1/xianyu/manage/items").status_code == 200
    assert client.post(
        "/api/v1/xianyu/manage/items/sync-page",
        json={"page": 1, "page_size": 20},
    ).status_code == 200
    assert client.post("/api/v1/xianyu/manage/items/sync-all").status_code == 200
    assert client.get("/api/v1/xianyu/manage/items/1001").status_code == 200
    assert client.put(
        "/api/v1/xianyu/manage/items/1001",
        json={"item_detail": "new detail"},
    ).status_code == 200
    assert client.put(
        "/api/v1/xianyu/manage/items/1001/multi-quantity-delivery",
        json={"enabled": True},
    ).status_code == 200
    assert client.get("/api/v1/xianyu/manage/delivery-rules").status_code == 200
    assert client.post(
        "/api/v1/xianyu/manage/delivery-rules",
        json={
            "name": "卡密发货",
            "enabled": True,
            "item_id": "1001",
            "keyword": "",
            "match_mode": "item_id",
            "delivery_text": "卡密：123",
            "send_chat_text": True,
            "send_dummy_ship": True,
        },
    ).status_code == 200
    assert client.get("/api/v1/xianyu/manage/runtime/status").status_code == 200
    assert client.get("/api/v1/xianyu/manage/runtime/executions").status_code == 200

    app.dependency_overrides.clear()
