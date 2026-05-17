import json
import time
from pathlib import Path
from typing import Iterable

from app.modules.xianyu.schemas import XianyuManageItem, XianyuManageItemPage


class XianyuItemStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        raw = self.path.read_text(encoding="utf-8").strip()
        return json.loads(raw or "[]")

    def _save(self, items: list[dict]) -> None:
        self.path.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_items(self, page: int = 1, page_size: int = 100) -> XianyuManageItemPage:
        page = max(int(page or 1), 1)
        page_size = max(int(page_size or 100), 1)
        raw = [XianyuManageItem(**item) for item in self._load()]
        start = (page - 1) * page_size
        end = start + page_size
        current = raw[start:end]
        return XianyuManageItemPage(
            items=current,
            total=len(raw),
            page=page,
            page_size=page_size,
            has_more=end < len(raw),
        )

    def get_item(self, item_id: str) -> XianyuManageItem | None:
        normalized = str(item_id or "").strip()
        if not normalized:
            return None
        for item in self._load():
            if str(item.get("item_id") or "").strip() == normalized:
                return XianyuManageItem(**item)
        return None

    def upsert_items(self, payloads: Iterable[dict]) -> list[XianyuManageItem]:
        now = int(time.time())
        current = {str(item.get("item_id") or "").strip(): item for item in self._load()}
        for payload in payloads:
            item_id = str((payload or {}).get("item_id") or "").strip()
            if not item_id:
                continue
            existing = current.get(item_id, {})
            current[item_id] = {
                "item_id": item_id,
                "item_title": str(payload.get("item_title") or existing.get("item_title") or ""),
                "item_price": str(payload.get("item_price") or existing.get("item_price") or ""),
                "item_image": str(payload.get("item_image") or existing.get("item_image") or ""),
                "item_status": str(payload.get("item_status") or existing.get("item_status") or ""),
                "item_detail": str(payload.get("item_detail") or existing.get("item_detail") or ""),
                "multi_quantity_delivery": bool(
                    payload.get("multi_quantity_delivery", existing.get("multi_quantity_delivery", False))
                ),
                "synced_at": now,
                "updated_at": int(existing.get("updated_at") or now),
            }
        ordered = list(current.values())
        self._save(ordered)
        return [XianyuManageItem(**item) for item in ordered]

    def update_item(self, item_id: str, *, item_detail: str) -> XianyuManageItem | None:
        normalized = str(item_id or "").strip()
        if not normalized:
            return None
        items = self._load()
        now = int(time.time())
        for item in items:
            if str(item.get("item_id") or "").strip() != normalized:
                continue
            item["item_detail"] = str(item_detail or "")
            item["updated_at"] = now
            self._save(items)
            return XianyuManageItem(**item)
        return None

    def set_multi_quantity_delivery(self, item_id: str, enabled: bool) -> XianyuManageItem | None:
        normalized = str(item_id or "").strip()
        if not normalized:
            return None
        items = self._load()
        now = int(time.time())
        for item in items:
            if str(item.get("item_id") or "").strip() != normalized:
                continue
            item["multi_quantity_delivery"] = bool(enabled)
            item["updated_at"] = now
            self._save(items)
            return XianyuManageItem(**item)
        return None

    def delete_item(self, item_id: str) -> bool:
        normalized = str(item_id or "").strip()
        if not normalized:
            return False
        items = self._load()
        filtered = [item for item in items if str(item.get("item_id") or "").strip() != normalized]
        if len(filtered) == len(items):
            return False
        self._save(filtered)
        return True

    def polish_item(self, item_id: str) -> bool:
        """商品擦亮 - 触发闲鱼平台的商品刷新排序逻辑（不修改本地数据）"""
        normalized = str(item_id or "").strip()
        if not normalized:
            return False
        items = self._load()
        polished = False
        now = int(time.time())
        for item in items:
            if str(item.get("item_id") or "").strip() == normalized:
                item["polished_at"] = now
                polished = True
                break
        if polished:
            self._save(items)
        return polished

    def polish_all_items(self) -> dict[str, int]:
        """擦亮所有商品"""
        items = self._load()
        if not items:
            return {"total": 0, "polished": 0}
        now = int(time.time())
        polished_count = 0
        for item in items:
            item["polished_at"] = now
            polished_count += 1
        self._save(items)
        return {"total": len(items), "polished": polished_count}
