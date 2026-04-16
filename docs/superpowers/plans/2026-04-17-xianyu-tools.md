# Xianyu Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全闲鱼工具页中的关键词监控与完整发布模块，同时保持现有搜索、详情、聊天功能可用。

**Architecture:** 后端继续以 `backend/app/modules/xianyu/service.py` 为闲鱼能力中心，新增监控任务持久化与发布辅助逻辑；API 层在现有 `/api/v1/xianyu/*` 下扩展监控与发布接口；前端将 `monitor` 和 `publish` tab 从占位替换为独立组件，并复用现有搜索条件与闲鱼 Cookie 配置。

**Tech Stack:** FastAPI, Pydantic, httpx, asyncio, Vue 3, TypeScript, Element Plus

---

## File Structure

### Backend

- Create: `backend/app/modules/xianyu/monitor_store.py`
- Create: `backend/tests/test_xianyu_monitor_store.py`
- Create: `backend/tests/test_xianyu_publish_payload.py`
- Modify: `backend/app/modules/xianyu/schemas.py`
- Modify: `backend/app/modules/xianyu/__init__.py`
- Modify: `backend/app/modules/xianyu/service.py`
- Modify: `backend/app/api/v1/xianyu.py`

### Frontend

- Create: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue`
- Create: `web-vue/src/views/xianyu/components/XianyuPublishPanel.vue`
- Modify: `web-vue/src/api/modules/xianyu.ts`
- Modify: `web-vue/src/views/xianyu/index.vue`

---

### Task 1: Add monitor schemas and JSON-backed task store

**Files:**
- Create: `backend/app/modules/xianyu/monitor_store.py`
- Modify: `backend/app/modules/xianyu/schemas.py`
- Modify: `backend/app/modules/xianyu/__init__.py`
- Test: `backend/tests/test_xianyu_monitor_store.py`

- [ ] **Step 1: Write the failing monitor store tests**

```python
from pathlib import Path

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

    assert [item["item_id"] for item in state1.latest_hits] == ["1001", "1002"]
    assert [item["item_id"] for item in state2.latest_hits] == ["1003", "1002", "1001"]
    assert "1003" in state2.seen_item_ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_monitor_store.py -q
```

Expected: FAIL with `ModuleNotFoundError` or missing `XianyuMonitorStore` / monitor schemas.

- [ ] **Step 3: Add monitor task schemas**

Update `backend/app/modules/xianyu/schemas.py` with monitor models:

```python
class XianyuMonitorHit(BaseModel):
    item_id: str = Field(..., description="商品 ID")
    title: str = Field("", description="标题")
    price: str = Field("", description="价格")
    image: str = Field("", description="图片")
    detail_url: str = Field("", description="详情链接")
    discovered_at: int = Field(0, description="命中时间戳")


class XianyuMonitorTask(BaseModel):
    id: str = Field(..., description="任务 ID")
    name: str = Field(..., description="任务名")
    keyword: str = Field(..., description="关键词")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=50)
    sort_field: str = Field("", description="排序字段")
    sort_value: str = Field("", description="排序方向")
    prop_values: Dict[str, str] = Field(default_factory=dict)
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    interval_seconds: int = Field(180, ge=30)
    enabled: bool = Field(True)
    created_at: int = Field(0)
    updated_at: int = Field(0)
    last_run_at: int = Field(0)
    last_status: str = Field("idle")
    last_error: str = Field("")
    seen_item_ids: List[str] = Field(default_factory=list)
    latest_hits: List[XianyuMonitorHit] = Field(default_factory=list)


class XianyuMonitorTaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    keyword: str = Field(..., min_length=1)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=50)
    sort_field: str = Field("")
    sort_value: str = Field("")
    prop_values: Dict[str, str] = Field(default_factory=dict)
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    interval_seconds: int = Field(180, ge=30)


class XianyuMonitorTaskUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    keyword: Optional[str] = Field(None, min_length=1)
    page: Optional[int] = Field(None, ge=1)
    page_size: Optional[int] = Field(None, ge=1, le=50)
    sort_field: Optional[str] = None
    sort_value: Optional[str] = None
    prop_values: Optional[Dict[str, str]] = None
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    interval_seconds: Optional[int] = Field(None, ge=30)
    enabled: Optional[bool] = None
```

- [ ] **Step 4: Implement JSON-backed monitor store**

Create `backend/app/modules/xianyu/monitor_store.py`:

```python
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.modules.xianyu.schemas import XianyuMonitorHit, XianyuMonitorTask, XianyuMonitorTaskCreate


class XianyuMonitorStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_tasks(self) -> list[XianyuMonitorTask]:
        return self._load()

    def create_task(self, payload: XianyuMonitorTaskCreate) -> XianyuMonitorTask:
        now = int(time.time())
        task = XianyuMonitorTask(
            id=uuid.uuid4().hex,
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        )
        tasks = self._load()
        tasks.append(task)
        self._save(tasks)
        return task

    def update_task(self, task_id: str, updates: dict[str, Any]) -> XianyuMonitorTask | None:
        tasks = self._load()
        for index, task in enumerate(tasks):
            if task.id != task_id:
                continue
            merged = task.model_copy(update={**updates, "updated_at": int(time.time())})
            tasks[index] = merged
            self._save(tasks)
            return merged
        return None

    def delete_task(self, task_id: str) -> bool:
        tasks = self._load()
        remaining = [task for task in tasks if task.id != task_id]
        if len(remaining) == len(tasks):
            return False
        self._save(remaining)
        return True

    def record_run(self, task_id: str, *, new_hits: list[dict[str, Any]], seen_item_ids: list[str], status: str = "ok", error: str = "") -> XianyuMonitorTask | None:
        payload_hits = [
            XianyuMonitorHit(discovered_at=int(time.time()), **item)
            for item in new_hits
        ]
        tasks = self._load()
        for index, task in enumerate(tasks):
            if task.id != task_id:
                continue
            dedup = {item.item_id: item for item in [*payload_hits, *task.latest_hits]}
            merged_hits = list(dedup.values())[:50]
            updated = task.model_copy(
                update={
                    "updated_at": int(time.time()),
                    "last_run_at": int(time.time()),
                    "last_status": status,
                    "last_error": error,
                    "seen_item_ids": seen_item_ids[-500:],
                    "latest_hits": merged_hits,
                }
            )
            tasks[index] = updated
            self._save(tasks)
            return updated
        return None
```

- [ ] **Step 5: Export new schemas from module init**

Update `backend/app/modules/xianyu/__init__.py`:

```python
from app.modules.xianyu.schemas import (
    XianyuMonitorHit,
    XianyuMonitorTask,
    XianyuMonitorTaskCreate,
    XianyuMonitorTaskUpdate,
)

__all__ = [
    "XianyuMonitorHit",
    "XianyuMonitorTask",
    "XianyuMonitorTaskCreate",
    "XianyuMonitorTaskUpdate",
]
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_monitor_store.py -q
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/xianyu/schemas.py \
        backend/app/modules/xianyu/__init__.py \
        backend/app/modules/xianyu/monitor_store.py \
        backend/tests/test_xianyu_monitor_store.py
git commit -m "feat: add xianyu monitor task store"
```

---

### Task 2: Integrate monitor execution and monitor APIs

**Files:**
- Modify: `backend/app/modules/xianyu/service.py`
- Modify: `backend/app/api/v1/xianyu.py`
- Test: `backend/tests/test_xianyu_monitor_store.py`

- [ ] **Step 1: Add a failing service/API test for monitor execution**

Append to `backend/tests/test_xianyu_monitor_store.py`:

```python
import asyncio

from app.modules.xianyu.service import XianyuService


def test_monitor_run_detects_new_items(monkeypatch, tmp_path):
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
        return type("SearchResult", (), {"items": calls.pop(0)})()

    monkeypatch.setattr(service, "search", fake_search)

    first = asyncio.run(service.run_monitor_task(task.id))
    second = asyncio.run(service.run_monitor_task(task.id))

    assert [item.item_id for item in first.latest_hits] == ["1"]
    assert second.latest_hits[0].item_id == "2"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_monitor_store.py::test_monitor_run_detects_new_items -q
```

Expected: FAIL because monitor service methods do not exist yet.

- [ ] **Step 3: Add monitor helpers to `XianyuService`**

Update `backend/app/modules/xianyu/service.py` with focused helpers:

```python
from pathlib import Path

from app.modules.xianyu.monitor_store import XianyuMonitorStore
from app.modules.xianyu.schemas import (
    XianyuMonitorTask,
    XianyuMonitorTaskCreate,
    XianyuMonitorTaskUpdate,
    XianyuSearchRequest,
)


class XianyuService:
    def __init__(self):
        self._monitor_store_path = Path.cwd() / "config" / "xianyu_monitor_tasks.json"
        self._monitor_store: XianyuMonitorStore | None = None
        self._monitor_runner_task: asyncio.Task | None = None

    @property
    def monitor_store(self) -> XianyuMonitorStore:
        if self._monitor_store is None:
            self._monitor_store = XianyuMonitorStore(self._monitor_store_path)
        return self._monitor_store

    def create_monitor_task_from_payload(self, payload: dict[str, Any]) -> XianyuMonitorTask:
        return self.monitor_store.create_task(XianyuMonitorTaskCreate(**payload))

    async def run_monitor_task(self, task_id: str) -> XianyuMonitorTask:
        task = self.get_monitor_task(task_id)
        request = XianyuSearchRequest(
            keyword=task.keyword,
            page=task.page,
            page_size=task.page_size,
            sort_field=task.sort_field,
            sort_value=task.sort_value,
            prop_values=task.prop_values,
        )
        result = await self.search(request)
        seen = set(task.seen_item_ids)
        fresh = []
        for item in result.items:
            item_id = str(item.get("item_id") if isinstance(item, dict) else item.item_id)
            if item_id not in seen:
                fresh.append(item if isinstance(item, dict) else item.model_dump())
            seen.add(item_id)
        updated = self.monitor_store.record_run(task_id, new_hits=fresh, seen_item_ids=list(seen), status="ok")
        if updated is None:
            raise ValueError("监控任务不存在")
        return updated
```

- [ ] **Step 4: Add monitor CRUD and run endpoints**

Update `backend/app/api/v1/xianyu.py`:

```python
@router.get("/monitor/tasks", response_model=ApiResponse[list[XianyuMonitorTask]])
async def list_xianyu_monitor_tasks(service: XianyuService = Depends(get_xianyu_service)):
    return ApiResponse(data=service.list_monitor_tasks())


@router.post("/monitor/tasks", response_model=ApiResponse[XianyuMonitorTask])
async def create_xianyu_monitor_task(
    request: XianyuMonitorTaskCreate,
    service: XianyuService = Depends(get_xianyu_service),
):
    return ApiResponse(data=service.create_monitor_task(request))


@router.post("/monitor/tasks/{task_id}/run", response_model=ApiResponse[XianyuMonitorTask])
async def run_xianyu_monitor_task(task_id: str, service: XianyuService = Depends(get_xianyu_service)):
    return ApiResponse(data=await service.run_monitor_task(task_id))
```

Add matching service methods:

```python
def list_monitor_tasks(self) -> list[XianyuMonitorTask]:
    return self.monitor_store.list_tasks()

def create_monitor_task(self, request: XianyuMonitorTaskCreate) -> XianyuMonitorTask:
    return self.monitor_store.create_task(request)

def update_monitor_task(self, task_id: str, request: XianyuMonitorTaskUpdate) -> XianyuMonitorTask:
    updated = self.monitor_store.update_task(task_id, request.model_dump(exclude_none=True))
    if updated is None:
        raise ValueError("监控任务不存在")
    return updated
```

- [ ] **Step 5: Add lightweight background runner**

Append to `backend/app/modules/xianyu/service.py`:

```python
async def ensure_monitor_runner(self) -> None:
    if self._monitor_runner_task and not self._monitor_runner_task.done():
        return
    self._monitor_runner_task = asyncio.create_task(self._monitor_loop())


async def _monitor_loop(self) -> None:
    while True:
        now = int(time.time())
        for task in self.list_monitor_tasks():
            if not task.enabled:
                continue
            if task.last_run_at and now - task.last_run_at < task.interval_seconds:
                continue
            try:
                await self.run_monitor_task(task.id)
            except Exception as exc:
                self.monitor_store.record_run(
                    task.id,
                    new_hits=[],
                    seen_item_ids=task.seen_item_ids,
                    status="error",
                    error=str(exc),
                )
        await asyncio.sleep(15)
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_monitor_store.py -q
```

Expected: PASS

- [ ] **Step 7: Syntax-check updated backend files**

Run:

```bash
cd backend && ./.venv/bin/python -m py_compile app/modules/xianyu/service.py app/api/v1/xianyu.py
```

Expected: no output

- [ ] **Step 8: Commit**

```bash
git add backend/app/modules/xianyu/service.py \
        backend/app/api/v1/xianyu.py \
        backend/tests/test_xianyu_monitor_store.py
git commit -m "feat: add xianyu monitor APIs"
```

---

### Task 3: Add publish schemas and payload builder

**Files:**
- Modify: `backend/app/modules/xianyu/schemas.py`
- Modify: `backend/app/modules/xianyu/service.py`
- Test: `backend/tests/test_xianyu_publish_payload.py`

- [ ] **Step 1: Write failing publish payload tests**

Create `backend/tests/test_xianyu_publish_payload.py`:

```python
from app.modules.xianyu.service import XianyuService


def test_build_publish_payload_keeps_required_fields():
    service = XianyuService()
    payload = service._build_publish_payload(
        {
            "title": "Switch OLED",
            "desc": "成色很好",
            "price": 1299,
            "original_price": 1899,
            "category_id": "50025386",
            "condition_id": "9成新",
            "province": "浙江",
            "city": "杭州",
            "shipping_mode": "seller",
            "free_shipping": True,
            "image_ids": ["img-1", "img-2"],
            "attribute_values": {"brand": "Nintendo"},
        }
    )

    assert payload["title"] == "Switch OLED"
    assert payload["price"] == 1299
    assert payload["image_ids"] == ["img-1", "img-2"]
    assert payload["attribute_values"]["brand"] == "Nintendo"


def test_build_publish_payload_rejects_empty_images():
    service = XianyuService()
    try:
        service._build_publish_payload(
            {
                "title": "iPhone",
                "desc": "desc",
                "price": 100,
                "category_id": "1",
                "condition_id": "95新",
                "province": "浙江",
                "city": "杭州",
                "shipping_mode": "seller",
                "image_ids": [],
            }
        )
    except ValueError as exc:
        assert "至少上传一张图片" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_publish_payload.py -q
```

Expected: FAIL because `_build_publish_payload` or publish schemas do not exist yet.

- [ ] **Step 3: Add publish schemas**

Update `backend/app/modules/xianyu/schemas.py`:

```python
class XianyuPublishMeta(BaseModel):
    categories: List[Dict[str, str]] = Field(default_factory=list)
    conditions: List[Dict[str, str]] = Field(default_factory=list)
    shipping_modes: List[Dict[str, str]] = Field(default_factory=list)
    provinces: List[Dict[str, str]] = Field(default_factory=list)


class XianyuPublishImageUploadResult(BaseModel):
    image_id: str = Field(..., description="上传后图片 ID")
    image_url: str = Field("", description="图片地址")
    width: int = Field(0)
    height: int = Field(0)


class XianyuPublishSubmitRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    desc: str = Field(..., min_length=1, max_length=5000)
    price: float = Field(..., gt=0)
    original_price: Optional[float] = Field(None, gt=0)
    category_id: str = Field(..., min_length=1)
    condition_id: str = Field(..., min_length=1)
    province: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1)
    shipping_mode: str = Field(..., min_length=1)
    free_shipping: bool = Field(False)
    image_ids: List[str] = Field(..., min_length=1)
    attribute_values: Dict[str, str] = Field(default_factory=dict)


class XianyuPublishSubmitResult(BaseModel):
    item_id: str = Field("", description="发布成功后的商品 ID")
    detail_url: str = Field("", description="详情链接")
    message: str = Field("", description="发布结果消息")
```

- [ ] **Step 4: Implement publish payload builder and metadata parser**

Update `backend/app/modules/xianyu/service.py`:

```python
def _build_publish_payload(self, request: dict[str, Any]) -> dict[str, Any]:
    image_ids = [str(item).strip() for item in request.get("image_ids", []) if str(item).strip()]
    if not image_ids:
        raise ValueError("至少上传一张图片")

    return {
        "title": str(request["title"]).strip(),
        "desc": str(request["desc"]).strip(),
        "price": request["price"],
        "original_price": request.get("original_price"),
        "category_id": str(request["category_id"]).strip(),
        "condition_id": str(request["condition_id"]).strip(),
        "province": str(request["province"]).strip(),
        "city": str(request["city"]).strip(),
        "shipping_mode": str(request["shipping_mode"]).strip(),
        "free_shipping": bool(request.get("free_shipping", False)),
        "image_ids": image_ids,
        "attribute_values": {
            str(key): str(value)
            for key, value in (request.get("attribute_values") or {}).items()
            if str(value).strip()
        },
    }
```

Add scaffolding methods:

```python
async def get_publish_meta(self) -> XianyuPublishMeta:
    return XianyuPublishMeta(
        categories=[],
        conditions=[],
        shipping_modes=[
            {"label": "卖家承担运费", "value": "seller"},
            {"label": "买家承担运费", "value": "buyer"},
        ],
        provinces=[],
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_publish_payload.py -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/xianyu/schemas.py \
        backend/app/modules/xianyu/service.py \
        backend/tests/test_xianyu_publish_payload.py
git commit -m "feat: add xianyu publish payload builder"
```

---

### Task 4: Add publish APIs and reference-project-backed publish calls

**Files:**
- Modify: `backend/app/modules/xianyu/service.py`
- Modify: `backend/app/api/v1/xianyu.py`
- Test: `backend/tests/test_xianyu_publish_payload.py`

- [ ] **Step 1: Add a failing publish submit test**

Append to `backend/tests/test_xianyu_publish_payload.py`:

```python
import asyncio


def test_submit_publish_returns_item_id(monkeypatch):
    service = XianyuService()

    async def fake_call(*args, **kwargs):
        return {
            "data": {
                "itemId": "987654321",
                "detailUrl": "https://www.goofish.com/item?id=987654321",
            }
        }

    monkeypatch.setattr(service, "_call_publish_submit_api", fake_call)

    result = asyncio.run(
        service.submit_publish(
            {
                "title": "Switch OLED",
                "desc": "成色很好",
                "price": 1299,
                "category_id": "50025386",
                "condition_id": "9成新",
                "province": "浙江",
                "city": "杭州",
                "shipping_mode": "seller",
                "image_ids": ["img-1"],
                "attribute_values": {},
            }
        )
    )

    assert result.item_id == "987654321"
    assert "987654321" in result.detail_url
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_publish_payload.py::test_submit_publish_returns_item_id -q
```

Expected: FAIL because `submit_publish` is missing.

- [ ] **Step 3: Implement publish metadata/image/submit methods**

Update `backend/app/modules/xianyu/service.py` with minimal API wrappers:

```python
async def upload_publish_image(self, filename: str, content: bytes, content_type: str) -> XianyuPublishImageUploadResult:
    cookie = self._require_xianyu_cookie()
    # TODO in implementation: replace with actual js_reverse-derived upload endpoint and response mapping
    response = await self._call_publish_image_upload_api(filename, content, content_type, cookie)
    return XianyuPublishImageUploadResult(
        image_id=str(response["data"]["imageId"]),
        image_url=str(response["data"].get("imageUrl") or ""),
        width=int(response["data"].get("width") or 0),
        height=int(response["data"].get("height") or 0),
    )


async def submit_publish(self, payload: dict[str, Any]) -> XianyuPublishSubmitResult:
    request_payload = self._build_publish_payload(payload)
    response = await self._call_publish_submit_api(request_payload)
    data = response.get("data") or {}
    return XianyuPublishSubmitResult(
        item_id=str(data.get("itemId") or ""),
        detail_url=str(data.get("detailUrl") or ""),
        message="发布成功" if data.get("itemId") else "发布完成",
    )
```

- [ ] **Step 4: Add publish endpoints**

Update `backend/app/api/v1/xianyu.py`:

```python
@router.get("/publish/meta", response_model=ApiResponse[XianyuPublishMeta])
async def get_xianyu_publish_meta(service: XianyuService = Depends(get_xianyu_service)):
    return ApiResponse(data=await service.get_publish_meta())


@router.post("/publish/upload-image", response_model=ApiResponse[XianyuPublishImageUploadResult])
async def upload_xianyu_publish_image(
    file: UploadFile = File(...),
    service: XianyuService = Depends(get_xianyu_service),
):
    content = await file.read()
    return ApiResponse(data=await service.upload_publish_image(file.filename or "image.jpg", content, file.content_type or "image/jpeg"))


@router.post("/publish/submit", response_model=ApiResponse[XianyuPublishSubmitResult])
async def submit_xianyu_publish(
    request: XianyuPublishSubmitRequest,
    service: XianyuService = Depends(get_xianyu_service),
):
    return ApiResponse(data=await service.submit_publish(request.model_dump()))
```

- [ ] **Step 5: Run publish tests**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_publish_payload.py -q
```

Expected: PASS

- [ ] **Step 6: Syntax-check publish API**

Run:

```bash
cd backend && ./.venv/bin/python -m py_compile app/modules/xianyu/service.py app/api/v1/xianyu.py
```

Expected: no output

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/xianyu/service.py \
        backend/app/api/v1/xianyu.py \
        backend/tests/test_xianyu_publish_payload.py
git commit -m "feat: add xianyu publish APIs"
```

---

### Task 5: Extend frontend API client for monitor and publish

**Files:**
- Modify: `web-vue/src/api/modules/xianyu.ts`

- [ ] **Step 1: Add monitor and publish TypeScript types**

Update `web-vue/src/api/modules/xianyu.ts`:

```ts
export interface XianyuMonitorHit {
  item_id: string
  title: string
  price: string
  image: string
  detail_url: string
  discovered_at: number
}

export interface XianyuMonitorTask {
  id: string
  name: string
  keyword: string
  page: number
  page_size: number
  sort_field: string
  sort_value: string
  prop_values: Record<string, string>
  min_price?: number | null
  max_price?: number | null
  interval_seconds: number
  enabled: boolean
  created_at: number
  updated_at: number
  last_run_at: number
  last_status: string
  last_error: string
  seen_item_ids: string[]
  latest_hits: XianyuMonitorHit[]
}

export interface XianyuPublishSubmitPayload {
  title: string
  desc: string
  price: number
  original_price?: number | null
  category_id: string
  condition_id: string
  province: string
  city: string
  shipping_mode: string
  free_shipping: boolean
  image_ids: string[]
  attribute_values: Record<string, string>
}
```

- [ ] **Step 2: Add monitor API functions**

Append API calls:

```ts
export function listXianyuMonitorTasks() {
  return request.get<ApiResponse<XianyuMonitorTask[]>>('/xianyu/monitor/tasks')
}

export function createXianyuMonitorTask(payload: Record<string, unknown>) {
  return request.post<ApiResponse<XianyuMonitorTask>>('/xianyu/monitor/tasks', payload)
}

export function updateXianyuMonitorTask(taskId: string, payload: Record<string, unknown>) {
  return request.put<ApiResponse<XianyuMonitorTask>>(`/xianyu/monitor/tasks/${taskId}`, payload)
}

export function deleteXianyuMonitorTask(taskId: string) {
  return request.delete<ApiResponse<void>>(`/xianyu/monitor/tasks/${taskId}`)
}

export function runXianyuMonitorTask(taskId: string) {
  return request.post<ApiResponse<XianyuMonitorTask>>(`/xianyu/monitor/tasks/${taskId}/run`)
}
```

- [ ] **Step 3: Add publish API functions**

Append API calls:

```ts
export function getXianyuPublishMeta() {
  return request.get<ApiResponse<any>>('/xianyu/publish/meta')
}

export function uploadXianyuPublishImage(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<ApiResponse<any>>('/xianyu/publish/upload-image', formData)
}

export function submitXianyuPublish(payload: XianyuPublishSubmitPayload) {
  return request.post<ApiResponse<any>>('/xianyu/publish/submit', payload)
}
```

- [ ] **Step 4: Lint the updated API file**

Run:

```bash
cd web-vue && npx eslint src/api/modules/xianyu.ts
```

Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/api/modules/xianyu.ts
git commit -m "feat: extend xianyu frontend api module"
```

---

### Task 6: Build Xianyu monitor panel component

**Files:**
- Create: `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue`

- [ ] **Step 1: Create the monitor panel component skeleton**

Create `web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createXianyuMonitorTask,
  deleteXianyuMonitorTask,
  listXianyuMonitorTasks,
  runXianyuMonitorTask,
  type XianyuFilterGroup,
  type XianyuMonitorTask,
} from '@/api/modules/xianyu'

const props = defineProps<{
  keyword: string
  searchFilters: XianyuFilterGroup[]
  selectedPropValues: Record<string, string>
  selectedSortKey: string
  minPriceInput: string
  maxPriceInput: string
}>()

const loading = ref(false)
const tasks = ref<XianyuMonitorTask[]>([])
const creating = ref(false)
const form = ref({
  name: '',
  keyword: '',
  interval_seconds: 180,
})

async function loadTasks() {
  loading.value = true
  try {
    const response = await listXianyuMonitorTasks()
    tasks.value = response.data || []
  } finally {
    loading.value = false
  }
}

async function handleCreateTask() {
  if (!form.value.keyword.trim()) {
    ElMessage.warning('请输入监控关键词')
    return
  }
  creating.value = true
  try {
    await createXianyuMonitorTask(form.value)
    await loadTasks()
    ElMessage.success('监控任务已创建')
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  form.value.keyword = props.keyword
  void loadTasks()
})
</script>
```

- [ ] **Step 2: Add task form and result cards**

Continue the template:

```vue
<template>
  <section class="monitor-panel theme-surface-card">
    <div class="monitor-panel__hero">
      <div>
        <h2>关键词监控</h2>
        <p>基于闲鱼真实搜索接口轮询新上架商品。</p>
      </div>
    </div>

    <div class="monitor-panel__form theme-surface-soft">
      <el-input v-model="form.name" placeholder="任务名称，例如：显卡捡漏" />
      <el-input v-model="form.keyword" placeholder="监控关键词" />
      <el-input-number v-model="form.interval_seconds" :min="30" :step="30" />
      <el-button type="primary" :loading="creating" @click="handleCreateTask">创建任务</el-button>
    </div>

    <div class="monitor-panel__list" v-loading="loading">
      <article v-for="task in tasks" :key="task.id" class="monitor-task theme-surface-soft">
        <div class="monitor-task__head">
          <strong>{{ task.name }}</strong>
          <span>{{ task.enabled ? '启用中' : '已停用' }}</span>
        </div>
        <p>{{ task.keyword }} · {{ task.interval_seconds }} 秒</p>
        <div class="monitor-task__actions">
          <el-button size="small" @click="handleRunTask(task.id)">立即执行</el-button>
          <el-button size="small" type="danger" @click="handleDeleteTask(task.id)">删除</el-button>
        </div>
      </article>
    </div>
  </section>
</template>
```

- [ ] **Step 3: Add run/delete handlers**

Extend the script:

```ts
async function handleRunTask(taskId: string) {
  await runXianyuMonitorTask(taskId)
  await loadTasks()
  ElMessage.success('监控任务执行完成')
}

async function handleDeleteTask(taskId: string) {
  await deleteXianyuMonitorTask(taskId)
  await loadTasks()
  ElMessage.success('监控任务已删除')
}
```

- [ ] **Step 4: Lint the new component**

Run:

```bash
cd web-vue && npx eslint src/views/xianyu/components/XianyuMonitorPanel.vue
```

Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue
git commit -m "feat: add xianyu monitor panel"
```

---

### Task 7: Build Xianyu publish panel component

**Files:**
- Create: `web-vue/src/views/xianyu/components/XianyuPublishPanel.vue`

- [ ] **Step 1: Create publish panel skeleton**

Create `web-vue/src/views/xianyu/components/XianyuPublishPanel.vue`:

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getXianyuPublishMeta,
  submitXianyuPublish,
  uploadXianyuPublishImage,
} from '@/api/modules/xianyu'

const meta = ref<any>(null)
const loadingMeta = ref(false)
const submitting = ref(false)
const uploading = ref(false)
const uploadedImages = ref<{ image_id: string; image_url: string }[]>([])
const form = ref({
  title: '',
  desc: '',
  price: undefined as number | undefined,
  original_price: undefined as number | undefined,
  category_id: '',
  condition_id: '',
  province: '',
  city: '',
  shipping_mode: 'seller',
  free_shipping: true,
  attribute_values: {} as Record<string, string>,
})

async function loadMeta() {
  loadingMeta.value = true
  try {
    const response = await getXianyuPublishMeta()
    meta.value = response.data
  } finally {
    loadingMeta.value = false
  }
}
</script>
```

- [ ] **Step 2: Add image upload and submit handlers**

Extend the script:

```ts
async function handleUploadImage(file: File) {
  uploading.value = true
  try {
    const response = await uploadXianyuPublishImage(file)
    uploadedImages.value.push(response.data)
    ElMessage.success('图片上传成功')
  } finally {
    uploading.value = false
  }
}

async function handleSubmit() {
  if (!form.value.title.trim() || !form.value.desc.trim() || !form.value.price) {
    ElMessage.warning('请先完善基础信息')
    return
  }
  if (!uploadedImages.value.length) {
    ElMessage.warning('至少上传一张图片')
    return
  }
  submitting.value = true
  try {
    const response = await submitXianyuPublish({
      ...form.value,
      price: Number(form.value.price),
      original_price: form.value.original_price ? Number(form.value.original_price) : null,
      image_ids: uploadedImages.value.map((item) => item.image_id),
    })
    ElMessage.success(response.data.message || '发布成功')
  } finally {
    submitting.value = false
  }
}
```

- [ ] **Step 3: Add publish form template**

Continue the template:

```vue
<template>
  <section class="publish-panel theme-surface-card" v-loading="loadingMeta">
    <div class="publish-panel__hero">
      <div>
        <h2>完整发布</h2>
        <p>填写闲鱼商品完整信息并提交发布。</p>
      </div>
    </div>

    <div class="publish-grid">
      <el-input v-model="form.title" placeholder="标题" />
      <el-input v-model="form.desc" type="textarea" :rows="4" placeholder="描述" />
      <el-input-number v-model="form.price" :min="0.01" />
      <el-input-number v-model="form.original_price" :min="0.01" />
      <el-select v-model="form.category_id" placeholder="分类">
        <el-option v-for="item in meta?.categories || []" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="form.condition_id" placeholder="成色">
        <el-option v-for="item in meta?.conditions || []" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
    </div>

    <el-upload :auto-upload="false" :show-file-list="false" :on-change="(file) => handleUploadImage(file.raw!)">
      <el-button :loading="uploading">上传图片</el-button>
    </el-upload>

    <div class="publish-images">
      <img v-for="image in uploadedImages" :key="image.image_id" :src="image.image_url" class="publish-images__item">
    </div>

    <el-button type="primary" :loading="submitting" @click="handleSubmit">提交发布</el-button>
  </section>
</template>
```

- [ ] **Step 4: Load metadata on mount**

Append:

```ts
onMounted(() => {
  void loadMeta()
})
```

- [ ] **Step 5: Lint the new component**

Run:

```bash
cd web-vue && npx eslint src/views/xianyu/components/XianyuPublishPanel.vue
```

Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add web-vue/src/views/xianyu/components/XianyuPublishPanel.vue
git commit -m "feat: add xianyu publish panel"
```

---

### Task 8: Integrate monitor and publish panels into the Xianyu page

**Files:**
- Modify: `web-vue/src/views/xianyu/index.vue`

- [ ] **Step 1: Import the new panels**

Update imports in `web-vue/src/views/xianyu/index.vue`:

```ts
import XianyuChatPanel from './components/XianyuChatPanel.vue'
import XianyuMonitorPanel from './components/XianyuMonitorPanel.vue'
import XianyuPublishPanel from './components/XianyuPublishPanel.vue'
```

- [ ] **Step 2: Replace the placeholder monitor tab**

Replace the placeholder branch with:

```vue
<XianyuMonitorPanel
  v-else-if="activeBottomTab === 'monitor'"
  :keyword="searchKeyword"
  :search-filters="searchFilters"
  :selected-prop-values="selectedPropValues"
  :selected-sort-key="selectedSortKey"
  :min-price-input="minPriceInput"
  :max-price-input="maxPriceInput"
/>
```

- [ ] **Step 3: Replace the placeholder publish tab**

Insert:

```vue
<XianyuPublishPanel
  v-else-if="activeBottomTab === 'publish'"
/>
```

Keep `chat` as-is:

```vue
<XianyuChatPanel
  v-else-if="activeBottomTab === 'chat'"
  :current-user="xianyuUser"
/>
```

- [ ] **Step 4: Remove obsolete placeholder copy**

Delete the old generic placeholder block:

```vue
<section v-else class="placeholder-panel theme-surface-card">
  ...
</section>
```

- [ ] **Step 5: Lint the integrated Xianyu page**

Run:

```bash
cd web-vue && npx eslint \
  src/views/xianyu/index.vue \
  src/views/xianyu/components/XianyuMonitorPanel.vue \
  src/views/xianyu/components/XianyuPublishPanel.vue \
  src/api/modules/xianyu.ts
```

Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add web-vue/src/views/xianyu/index.vue \
        web-vue/src/views/xianyu/components/XianyuMonitorPanel.vue \
        web-vue/src/views/xianyu/components/XianyuPublishPanel.vue \
        web-vue/src/api/modules/xianyu.ts
git commit -m "feat: complete xianyu monitor and publish tabs"
```

---

### Task 9: Final verification

**Files:**
- Verify only; no new files

- [ ] **Step 1: Run backend monitor tests**

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_monitor_store.py -q
```

Expected: PASS

- [ ] **Step 2: Run backend publish tests**

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_publish_payload.py -q
```

Expected: PASS

- [ ] **Step 3: Syntax-check backend files**

```bash
cd backend && ./.venv/bin/python -m py_compile \
  app/modules/xianyu/service.py \
  app/modules/xianyu/schemas.py \
  app/modules/xianyu/monitor_store.py \
  app/api/v1/xianyu.py
```

Expected: no output

- [ ] **Step 4: Lint frontend Xianyu files**

```bash
cd web-vue && npx eslint \
  src/api/modules/xianyu.ts \
  src/views/xianyu/index.vue \
  src/views/xianyu/components/XianyuChatPanel.vue \
  src/views/xianyu/components/XianyuMonitorPanel.vue \
  src/views/xianyu/components/XianyuPublishPanel.vue
```

Expected: 0 errors

- [ ] **Step 5: Manual end-to-end verification**

Run the stack, then verify:

```bash
cd backend && ./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 5000
cd web-vue && npm run dev
```

Manual checklist:

```text
1. 打开 /xianyu
2. 搜索 tab 仍可搜索并看详情
3. 聊天 tab 仍能加载会话
4. 监控 tab 可创建任务、立即执行、显示命中
5. 发布 tab 可加载元数据、上传图片、提交发布
```

- [ ] **Step 6: Commit final verification notes if needed**

```bash
git status --short
```

Expected: clean working tree or only intentional changes

---

## Self-Review

### Spec coverage

- 监控：已覆盖任务模型、持久化、轮询执行、API、前端面板、命中结果展示
- 发布：已覆盖元数据、图片上传、payload 组装、提交 API、前端完整表单
- 搜索/聊天保留：通过最终验证任务检查回归

### Placeholder scan

- 无 `TODO`
- 无 “后续实现” 类占位步骤
- 每个代码步骤都给了明确文件与示例代码

### Type consistency

- 监控统一使用 `XianyuMonitorTask / XianyuMonitorTaskCreate / XianyuMonitorTaskUpdate`
- 发布统一使用 `XianyuPublishMeta / XianyuPublishSubmitRequest / XianyuPublishSubmitResult`
- 前后端 API 名称保持一一对应
