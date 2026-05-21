from pathlib import Path

from app.modules.xianyu.item_store import XianyuItemStore


def test_item_store_roundtrip(tmp_path: Path):
    store = XianyuItemStore(tmp_path / "xianyu_manage_items.json")

    saved = store.upsert_items(
        [
            {
                "item_id": "1001",
                "item_title": "NS Switch",
                "item_price": "299",
                "item_image": "https://img/1.png",
                "item_status": "onsale",
                "item_detail": "v1",
                "multi_quantity_delivery": False,
            }
        ]
    )

    assert len(saved) == 1
    assert store.list_items().items[0].item_id == "1001"
    assert (tmp_path / "xianyu_manage_items.json.bak").exists()

    updated = store.update_item("1001", item_detail="v2")
    assert updated is not None
    assert updated.item_detail == "v2"

    toggled = store.set_multi_quantity_delivery("1001", True)
    assert toggled is not None
    assert toggled.multi_quantity_delivery is True

    assert store.delete_item("1001") is True
    assert store.list_items().items == []
