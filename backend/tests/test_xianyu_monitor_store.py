from pathlib import Path
import asyncio

from app.modules.xianyu.service import XianyuService
from app.modules.xianyu.monitor_store import XianyuMonitorStore
from app.modules.xianyu.schemas import XianyuMonitorTaskCreate


def test_monitor_store_create_update_delete_roundtrip(tmp_path: Path):
    store = XianyuMonitorStore(tmp_path / "xianyu_monitor_tasks.json")
    created = store.create_task(
        XianyuMonitorTaskCreate(
            name="显卡监控",
            keyword="4060",
            page=1,
            page_size=20,
            interval_seconds=180,
        )
    )

    assert created.id
    assert created.keyword == "4060"
    assert store.list_tasks()[0].id == created.id

    updated = store.update_task(created.id, {"enabled": False, "sort_field": "price"})
    assert updated is not None
    assert updated.enabled is False
    assert updated.sort_field == "price"

    assert store.delete_task(created.id) is True
    assert store.list_tasks() == []


def test_monitor_store_records_hits_without_duplicate_item_ids(tmp_path: Path):
    store = XianyuMonitorStore(tmp_path / "xianyu_monitor_tasks.json")
    task = store.create_task(
        XianyuMonitorTaskCreate(
            name="相机监控",
            keyword="索尼",
            interval_seconds=120,
        )
    )

    first = [{"item_id": "1001", "title": "A"}, {"item_id": "1002", "title": "B"}]
    second = [{"item_id": "1002", "title": "B"}, {"item_id": "1003", "title": "C"}]

    state1 = store.record_run(task.id, new_hits=first, seen_item_ids=["1001", "1002"])
    state2 = store.record_run(task.id, new_hits=second, seen_item_ids=["1001", "1002", "1003"])

    assert [item.item_id for item in state1.latest_hits] == ["1002", "1001"]
    assert [item.item_id for item in state2.latest_hits] == ["1003", "1002", "1001"]
    assert "1003" in state2.seen_item_ids


def test_monitor_run_detects_new_items(monkeypatch, tmp_path: Path):
    service = XianyuService()
    service._monitor_store_path = tmp_path / "xianyu_monitor_tasks.json"
    service._monitor_store = None

    task = service.create_monitor_task_from_payload(
        {
            "name": "笔记本监控",
            "keyword": "MacBook",
            "interval_seconds": 180,
        }
    )

    calls = [
        [{"item_id": "1", "title": "A", "price": "100", "image": "", "detail_url": "u1"}],
        [{"item_id": "1", "title": "A", "price": "100", "image": "", "detail_url": "u1"},
         {"item_id": "2", "title": "B", "price": "200", "image": "", "detail_url": "u2"}],
    ]

    async def fake_search(request):
        from app.modules.xianyu.schemas import XianyuSearchResult

        return XianyuSearchResult(
            keyword=request.keyword,
            items=calls.pop(0),
        )

    monkeypatch.setattr(service, "search", fake_search)

    first = asyncio.run(service.run_monitor_task(task.id))
    second = asyncio.run(service.run_monitor_task(task.id))

    assert [item.item_id for item in first.latest_hits] == ["1"]
    assert second.latest_hits[0].item_id == "2"
