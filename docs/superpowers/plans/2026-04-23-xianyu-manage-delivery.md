# Xianyu Manage + Auto Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Xianyu `publish` tab with a `manage` tab and ship a first usable management flow: item sync/editing, delivery rule CRUD, runtime status, and a minimal auto-delivery execution loop integrated into the current Xianyu stack.

**Architecture:** Keep the existing `xianyu` vertical slice and extend it with explicit store/runtime modules instead of importing the reference project whole. Reuse existing order/chat APIs in `XianyuService`, add local persistence for manage data, and expose the new capabilities under `/xianyu/manage/*` while the Vue page gets a dedicated `XianyuManagePanel` with three sub-panels.

**Tech Stack:** FastAPI, Pydantic, existing `XianyuService`, pytest, Vue 3 + Element Plus + TypeScript, Vite, Vitest + Vue Test Utils (to be added in this work).

---

## File Structure

### Backend files
- Modify: `backend/app/modules/xianyu/schemas.py`
- Modify: `backend/app/modules/xianyu/service.py`
- Modify: `backend/app/modules/xianyu/__init__.py`
- Modify: `backend/app/api/v1/xianyu.py`
- Create: `backend/app/modules/xianyu/item_store.py`
- Create: `backend/app/modules/xianyu/delivery_store.py`
- Create: `backend/app/modules/xianyu/delivery_runtime.py`
- Create: `backend/tests/test_xianyu_manage_item_store.py`
- Create: `backend/tests/test_xianyu_delivery_store.py`
- Create: `backend/tests/test_xianyu_manage_routes.py`
- Create: `backend/tests/test_xianyu_delivery_runtime.py`

### Frontend files
- Modify: `web-vue/package.json`
- Modify: `web-vue/src/api/modules/xianyu.ts`
- Modify: `web-vue/src/views/xianyu/index.vue`
- Create: `web-vue/src/views/xianyu/components/XianyuManagePanel.vue`
- Create: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue`
- Create: `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.vue`
- Create: `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.vue`
- Create: `web-vue/vitest.config.ts`
- Create: `web-vue/src/test/setup.ts`
- Create: `web-vue/src/views/xianyu/index.spec.ts`
- Create: `web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts`

---

### Task 1: Add backend data models and item/delivery stores

**Files:**
- Create: `backend/tests/test_xianyu_manage_item_store.py`
- Create: `backend/tests/test_xianyu_delivery_store.py`
- Modify: `backend/app/modules/xianyu/schemas.py`
- Create: `backend/app/modules/xianyu/item_store.py`
- Create: `backend/app/modules/xianyu/delivery_store.py`
- Modify: `backend/app/modules/xianyu/__init__.py`

- [ ] **Step 1: Write the failing item store test**

```python
from pathlib import Path

from app.modules.xianyu.item_store import XianyuItemStore


def test_item_store_roundtrip(tmp_path: Path):
    store = XianyuItemStore(tmp_path / 'xianyu_manage_items.json')

    saved = store.upsert_items([
        {
            'item_id': '1001',
            'item_title': 'NS Switch',
            'item_price': '299',
            'item_image': 'https://img/1.png',
            'item_status': 'onsale',
            'item_detail': 'v1',
            'multi_quantity_delivery': False,
        }
    ])

    assert len(saved) == 1
    assert store.list_items().items[0].item_id == '1001'

    updated = store.update_item('1001', item_detail='v2')
    assert updated is not None
    assert updated.item_detail == 'v2'

    toggled = store.set_multi_quantity_delivery('1001', True)
    assert toggled is not None
    assert toggled.multi_quantity_delivery is True

    assert store.delete_item('1001') is True
    assert store.list_items().items == []
```

- [ ] **Step 2: Write the failing delivery store test**

```python
from pathlib import Path

from app.modules.xianyu.delivery_store import XianyuDeliveryStore
from app.modules.xianyu.schemas import XianyuDeliveryRuleCreateRequest


def test_delivery_store_rule_and_execution_roundtrip(tmp_path: Path):
    store = XianyuDeliveryStore(
        rules_path=tmp_path / 'xianyu_delivery_rules.json',
        runtime_path=tmp_path / 'xianyu_delivery_runtime.json',
    )

    rule = store.create_rule(
        XianyuDeliveryRuleCreateRequest(
            name='卡密发货',
            enabled=True,
            match_mode='item_id',
            item_id='1001',
            keyword='',
            delivery_text='卡密：ABC-123',
            send_chat_text=True,
            send_dummy_ship=True,
        )
    )

    assert rule.id
    assert store.list_rules()[0].name == '卡密发货'

    toggled = store.toggle_rule(rule.id)
    assert toggled.enabled is False

    record = store.record_execution(
        rule_id=rule.id,
        rule_name=rule.name,
        order_id='order-1',
        item_id='1001',
        buyer_id='buyer-1',
        status='success',
        message='delivered',
    )
    assert record.status == 'success'

    runtime = store.get_runtime_status()
    assert runtime.recent_success_count == 1
    assert runtime.running is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run:
```bash
cd backend && pytest \
  tests/test_xianyu_manage_item_store.py \
  tests/test_xianyu_delivery_store.py -q
```

Expected: `ModuleNotFoundError` or import failures for the new store/schema symbols.

- [ ] **Step 4: Add the new schema types in `schemas.py`**

```python
class XianyuManageItem(BaseModel):
    item_id: str = Field(..., description='商品 ID')
    item_title: str = Field('', description='商品标题')
    item_price: str = Field('', description='商品价格')
    item_image: str = Field('', description='商品主图')
    item_status: str = Field('', description='商品状态')
    item_detail: str = Field('', description='商品详情文本')
    multi_quantity_delivery: bool = Field(False, description='是否启用多数量发货')
    synced_at: int = Field(0, description='最近同步时间')
    updated_at: int = Field(0, description='最近更新时间')


class XianyuManageItemPage(BaseModel):
    items: List[XianyuManageItem] = Field(default_factory=list)
    total: int = Field(0)
    page: int = Field(1)
    page_size: int = Field(20)
    has_more: bool = Field(False)


class XianyuManageItemUpdateRequest(BaseModel):
    item_detail: str = Field('', description='商品详情文本')


class XianyuManageItemSyncPageRequest(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class XianyuManageItemMultiQuantityUpdateRequest(BaseModel):
    enabled: bool = Field(False)


class XianyuDeliveryRule(BaseModel):
    id: str = Field(...)
    name: str = Field(...)
    enabled: bool = Field(True)
    item_id: str = Field('')
    keyword: str = Field('')
    match_mode: str = Field('item_id')
    delivery_text: str = Field('')
    send_chat_text: bool = Field(True)
    send_dummy_ship: bool = Field(True)
    created_at: int = Field(0)
    updated_at: int = Field(0)


class XianyuDeliveryRuleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    enabled: bool = Field(True)
    item_id: str = Field('')
    keyword: str = Field('')
    match_mode: str = Field('item_id')
    delivery_text: str = Field('', max_length=5000)
    send_chat_text: bool = Field(True)
    send_dummy_ship: bool = Field(True)


class XianyuDeliveryRuleUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    enabled: Optional[bool] = None
    item_id: Optional[str] = None
    keyword: Optional[str] = None
    match_mode: Optional[str] = None
    delivery_text: Optional[str] = Field(None, max_length=5000)
    send_chat_text: Optional[bool] = None
    send_dummy_ship: Optional[bool] = None


class XianyuDeliveryExecutionRecord(BaseModel):
    id: str = Field(...)
    rule_id: str = Field('')
    rule_name: str = Field('')
    order_id: str = Field('')
    item_id: str = Field('')
    buyer_id: str = Field('')
    status: str = Field('skipped')
    message: str = Field('')
    created_at: int = Field(0)


class XianyuDeliveryRuntimeStatus(BaseModel):
    running: bool = Field(False)
    last_event_at: int = Field(0)
    last_success_at: int = Field(0)
    last_failure_at: int = Field(0)
    last_error: str = Field('')
    enabled_rule_count: int = Field(0)
    recent_success_count: int = Field(0)
    recent_failure_count: int = Field(0)
```

- [ ] **Step 5: Implement `XianyuItemStore` and `XianyuDeliveryStore` minimally**

```python
# backend/app/modules/xianyu/item_store.py
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
        return json.loads(self.path.read_text(encoding='utf-8') or '[]')

    def _save(self, items: list[dict]) -> None:
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')

    def list_items(self, page: int = 1, page_size: int = 100) -> XianyuManageItemPage:
        raw = [XianyuManageItem(**item) for item in self._load()]
        start = max(page - 1, 0) * page_size
        end = start + page_size
        current = raw[start:end]
        return XianyuManageItemPage(
            items=current,
            total=len(raw),
            page=page,
            page_size=page_size,
            has_more=end < len(raw),
        )

    def upsert_items(self, payloads: Iterable[dict]) -> list[XianyuManageItem]:
        now = int(time.time())
        current = {item['item_id']: item for item in self._load()}
        for payload in payloads:
            item_id = str(payload.get('item_id') or '').strip()
            if not item_id:
                continue
            existing = current.get(item_id, {})
            current[item_id] = {
                **existing,
                **payload,
                'item_id': item_id,
                'synced_at': now,
                'updated_at': now if not existing else existing.get('updated_at', now),
            }
        ordered = list(current.values())
        self._save(ordered)
        return [XianyuManageItem(**item) for item in ordered]
```

```python
# backend/app/modules/xianyu/delivery_store.py
import json
import time
import uuid
from pathlib import Path

from app.modules.xianyu.schemas import (
    XianyuDeliveryExecutionRecord,
    XianyuDeliveryRule,
    XianyuDeliveryRuleCreateRequest,
    XianyuDeliveryRuntimeStatus,
)


class XianyuDeliveryStore:
    def __init__(self, rules_path: Path, runtime_path: Path):
        self.rules_path = Path(rules_path)
        self.runtime_path = Path(runtime_path)
        self.rules_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_path.parent.mkdir(parents=True, exist_ok=True)

    def create_rule(self, request: XianyuDeliveryRuleCreateRequest) -> XianyuDeliveryRule:
        now = int(time.time())
        rule = XianyuDeliveryRule(id=uuid.uuid4().hex, created_at=now, updated_at=now, **request.model_dump())
        rules = self._load_rules()
        rules.append(rule.model_dump())
        self._save_rules(rules)
        self._ensure_runtime_file()
        return rule
```

- [ ] **Step 6: Export the new types and stores**

```python
from app.modules.xianyu.item_store import XianyuItemStore
from app.modules.xianyu.delivery_store import XianyuDeliveryStore
```

Also append the new schemas/stores to `__all__` in `backend/app/modules/xianyu/__init__.py`.

- [ ] **Step 7: Run tests to verify they pass**

Run:
```bash
cd backend && pytest \
  tests/test_xianyu_manage_item_store.py \
  tests/test_xianyu_delivery_store.py -q
```

Expected: `2 passed`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/modules/xianyu/schemas.py \
  backend/app/modules/xianyu/item_store.py \
  backend/app/modules/xianyu/delivery_store.py \
  backend/app/modules/xianyu/__init__.py \
  backend/tests/test_xianyu_manage_item_store.py \
  backend/tests/test_xianyu_delivery_store.py

git commit -m "feat: add xianyu manage item and delivery stores"
```

---

### Task 2: Add service methods for manage items and sync actions

**Files:**
- Create: `backend/tests/test_xianyu_manage_routes.py`
- Modify: `backend/app/modules/xianyu/service.py`

- [ ] **Step 1: Write the failing service-facing route tests for item manage endpoints**

```python
from fastapi.testclient import TestClient

from app.api.deps import get_xianyu_service
from app.main import app


class FakeManageService:
    async def ensure_chat_ai_listener(self):
        return True

    def list_manage_items(self, page=1, page_size=20):
        return {
            'items': [
                {
                    'item_id': '1001',
                    'item_title': 'Switch',
                    'item_price': '299',
                    'item_image': '',
                    'item_status': 'onsale',
                    'item_detail': 'detail',
                    'multi_quantity_delivery': False,
                    'synced_at': 1,
                    'updated_at': 1,
                }
            ],
            'total': 1,
            'page': page,
            'page_size': page_size,
            'has_more': False,
        }

    async def sync_manage_items_page(self, page=1, page_size=20):
        return self.list_manage_items(page, page_size)

    async def sync_manage_items_all(self):
        return {'synced': 1, 'pages': 1}

    def get_manage_item(self, item_id: str):
        return self.list_manage_items()['items'][0]

    def update_manage_item(self, item_id: str, item_detail: str):
        item = self.list_manage_items()['items'][0]
        item['item_detail'] = item_detail
        return item

    def set_manage_item_multi_quantity_delivery(self, item_id: str, enabled: bool):
        item = self.list_manage_items()['items'][0]
        item['multi_quantity_delivery'] = enabled
        return item


def test_manage_item_routes_roundtrip():
    app.dependency_overrides[get_xianyu_service] = lambda: FakeManageService()
    client = TestClient(app)

    assert client.get('/api/v1/xianyu/manage/items').status_code == 200
    assert client.post('/api/v1/xianyu/manage/items/sync-page', json={'page': 1, 'page_size': 20}).status_code == 200
    assert client.post('/api/v1/xianyu/manage/items/sync-all').status_code == 200
    assert client.get('/api/v1/xianyu/manage/items/1001').status_code == 200
    assert client.put('/api/v1/xianyu/manage/items/1001', json={'item_detail': 'new detail'}).status_code == 200
    assert client.put('/api/v1/xianyu/manage/items/1001/multi-quantity-delivery', json={'enabled': True}).status_code == 200

    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:
```bash
cd backend && pytest tests/test_xianyu_manage_routes.py::test_manage_item_routes_roundtrip -q
```

Expected: `404` failures because `/xianyu/manage/items*` routes do not exist yet.

- [ ] **Step 3: Extend `XianyuService.__init__` with item/delivery store paths and accessors**

```python
self._item_store_path = Path.cwd() / 'config' / 'xianyu_manage_items.json'
self._delivery_rules_path = Path.cwd() / 'config' / 'xianyu_delivery_rules.json'
self._delivery_runtime_path = Path.cwd() / 'config' / 'xianyu_delivery_runtime.json'
self._item_store: XianyuItemStore | None = None
self._delivery_store: XianyuDeliveryStore | None = None
```

```python
@property
def item_store(self) -> XianyuItemStore:
    if self._item_store is None:
        self._item_store = XianyuItemStore(self._item_store_path)
    return self._item_store

@property
def delivery_store(self) -> XianyuDeliveryStore:
    if self._delivery_store is None:
        self._delivery_store = XianyuDeliveryStore(self._delivery_rules_path, self._delivery_runtime_path)
    return self._delivery_store
```

- [ ] **Step 4: Add minimal manage item service methods**

```python
def list_manage_items(self, page: int = 1, page_size: int = 20) -> XianyuManageItemPage:
    return self.item_store.list_items(page=page, page_size=page_size)


def get_manage_item(self, item_id: str) -> XianyuManageItem:
    item = self.item_store.get_item(item_id)
    if item is None:
        raise ValueError('商品不存在')
    return item


def update_manage_item(self, item_id: str, item_detail: str) -> XianyuManageItem:
    item = self.item_store.update_item(item_id, item_detail=item_detail)
    if item is None:
        raise ValueError('商品不存在')
    return item


def set_manage_item_multi_quantity_delivery(self, item_id: str, enabled: bool) -> XianyuManageItem:
    item = self.item_store.set_multi_quantity_delivery(item_id, enabled)
    if item is None:
        raise ValueError('商品不存在')
    return item
```

- [ ] **Step 5: Add sync methods that reuse current API calls and map into store payloads**

```python
async def sync_manage_items_page(self, page: int = 1, page_size: int = 20) -> XianyuManageItemPage:
    orders = await self.list_merchant_orders(page=1, page_size=1)
    _ = orders  # keep cookie validation behavior warm
    synced = self.item_store.upsert_items([])
    return self.item_store.list_items(page=page, page_size=page_size)
```

Replace the stub with a real call to a new helper (same task) that uses the seller item list endpoint and maps records into the fields required by `XianyuManageItem`.

```python
def _map_manage_item(self, raw: dict[str, Any]) -> dict[str, Any]:
    return {
        'item_id': str(raw.get('itemId') or '').strip(),
        'item_title': str(raw.get('title') or '').strip(),
        'item_price': str(raw.get('price') or '').strip(),
        'item_image': self._normalize_image_url(str(raw.get('picUrl') or '')),
        'item_status': str(raw.get('itemStatus') or '').strip(),
        'item_detail': str(raw.get('item_detail') or '').strip(),
        'multi_quantity_delivery': bool(raw.get('multi_quantity_delivery') or False),
    }
```

Also add:
- a seller item list API name/url constant
- a `sync_manage_items_all()` loop that pages until `has_more` is false
- `delete_manage_item(item_id)` service method for the later route task.

- [ ] **Step 6: Run the route test again to keep it red but closer**

Run:
```bash
cd backend && pytest tests/test_xianyu_manage_routes.py::test_manage_item_routes_roundtrip -q
```

Expected: still failing on missing routes, but import/service method errors should now be gone.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/xianyu/service.py backend/tests/test_xianyu_manage_routes.py

git commit -m "feat: add xianyu manage item service methods"
```

---

### Task 3: Add delivery rule APIs and runtime persistence surface

**Files:**
- Modify: `backend/tests/test_xianyu_manage_routes.py`
- Modify: `backend/app/modules/xianyu/service.py`
- Create: `backend/app/modules/xianyu/delivery_runtime.py`
- Create: `backend/tests/test_xianyu_delivery_runtime.py`

- [ ] **Step 1: Extend the failing route tests for delivery rules and runtime status**

```python
class FakeManageService(FakeManageService):
    def list_delivery_rules(self):
        return [{
            'id': 'rule-1',
            'name': '卡密发货',
            'enabled': True,
            'item_id': '1001',
            'keyword': '',
            'match_mode': 'item_id',
            'delivery_text': '卡密：123',
            'send_chat_text': True,
            'send_dummy_ship': True,
            'created_at': 1,
            'updated_at': 1,
        }]

    def create_delivery_rule(self, request):
        return self.list_delivery_rules()[0]

    def update_delivery_rule(self, rule_id, request):
        return self.list_delivery_rules()[0]

    def delete_delivery_rule(self, rule_id):
        return True

    def toggle_delivery_rule(self, rule_id):
        item = self.list_delivery_rules()[0]
        item['enabled'] = False
        return item

    def get_delivery_runtime_status(self):
        return {
            'running': False,
            'last_event_at': 0,
            'last_success_at': 0,
            'last_failure_at': 0,
            'last_error': '',
            'enabled_rule_count': 1,
            'recent_success_count': 0,
            'recent_failure_count': 0,
        }

    def list_delivery_executions(self, limit=20):
        return []
```

Add route assertions:

```python
assert client.get('/api/v1/xianyu/manage/delivery-rules').status_code == 200
assert client.post('/api/v1/xianyu/manage/delivery-rules', json={
    'name': '卡密发货',
    'enabled': True,
    'item_id': '1001',
    'keyword': '',
    'match_mode': 'item_id',
    'delivery_text': '卡密：123',
    'send_chat_text': True,
    'send_dummy_ship': True,
}).status_code == 200
assert client.get('/api/v1/xianyu/manage/runtime/status').status_code == 200
assert client.get('/api/v1/xianyu/manage/runtime/executions').status_code == 200
```

- [ ] **Step 2: Add the failing runtime unit test**

```python
from pathlib import Path

from app.modules.xianyu.delivery_runtime import XianyuDeliveryRuntime
from app.modules.xianyu.delivery_store import XianyuDeliveryStore
from app.modules.xianyu.item_store import XianyuItemStore
from app.modules.xianyu.schemas import XianyuDeliveryRuleCreateRequest


class FakeExecutor:
    def __init__(self):
        self.calls = []

    async def send_chat_and_ship(self, *, order_id: str, item_id: str, buyer_id: str, delivery_text: str):
        self.calls.append((order_id, item_id, buyer_id, delivery_text))
        return 'ok'


async def test_delivery_runtime_matches_rule_and_records_success(tmp_path: Path):
    item_store = XianyuItemStore(tmp_path / 'items.json')
    delivery_store = XianyuDeliveryStore(tmp_path / 'rules.json', tmp_path / 'runtime.json')
    delivery_store.create_rule(
        XianyuDeliveryRuleCreateRequest(
            name='按商品发货', enabled=True, item_id='1001', keyword='', match_mode='item_id',
            delivery_text='卡密 123', send_chat_text=True, send_dummy_ship=True,
        )
    )
    runtime = XianyuDeliveryRuntime(item_store=item_store, delivery_store=delivery_store)
    executor = FakeExecutor()

    await runtime.process_event(
        {'order_id': 'order-1', 'item_id': '1001', 'buyer_id': 'buyer-1', 'text': '我已付款'},
        executor=executor,
    )

    assert executor.calls == [('order-1', '1001', 'buyer-1', '卡密 123')]
    assert delivery_store.list_executions(limit=1)[0].status == 'success'
```

- [ ] **Step 3: Run tests to verify they fail**

Run:
```bash
cd backend && pytest \
  tests/test_xianyu_manage_routes.py \
  tests/test_xianyu_delivery_runtime.py -q
```

Expected: missing routes/runtime module failures.

- [ ] **Step 4: Implement service methods for rules and runtime reads**

```python
def list_delivery_rules(self) -> list[XianyuDeliveryRule]:
    return self.delivery_store.list_rules()


def create_delivery_rule(self, request: XianyuDeliveryRuleCreateRequest) -> XianyuDeliveryRule:
    return self.delivery_store.create_rule(request)


def update_delivery_rule(self, rule_id: str, request: XianyuDeliveryRuleUpdateRequest) -> XianyuDeliveryRule:
    rule = self.delivery_store.update_rule(rule_id, request.model_dump(exclude_none=True))
    if rule is None:
        raise ValueError('规则不存在')
    return rule


def delete_delivery_rule(self, rule_id: str) -> bool:
    return self.delivery_store.delete_rule(rule_id)


def toggle_delivery_rule(self, rule_id: str) -> XianyuDeliveryRule:
    rule = self.delivery_store.toggle_rule(rule_id)
    if rule is None:
        raise ValueError('规则不存在')
    return rule


def get_delivery_runtime_status(self) -> XianyuDeliveryRuntimeStatus:
    return self.delivery_store.get_runtime_status()


def list_delivery_executions(self, limit: int = 20) -> list[XianyuDeliveryExecutionRecord]:
    return self.delivery_store.list_executions(limit=limit)
```

- [ ] **Step 5: Implement the minimal runtime processor**

```python
# backend/app/modules/xianyu/delivery_runtime.py
class XianyuDeliveryRuntime:
    def __init__(self, *, item_store: XianyuItemStore, delivery_store: XianyuDeliveryStore):
        self.item_store = item_store
        self.delivery_store = delivery_store

    async def process_event(self, event: dict, executor) -> None:
        order_id = str(event.get('order_id') or '').strip()
        item_id = str(event.get('item_id') or '').strip()
        buyer_id = str(event.get('buyer_id') or '').strip()
        text = str(event.get('text') or '').strip()
        self.delivery_store.mark_runtime_event()

        matched = next(
            (
                rule for rule in self.delivery_store.list_rules()
                if rule.enabled and (
                    (rule.match_mode == 'item_id' and rule.item_id and rule.item_id == item_id) or
                    (rule.match_mode == 'keyword' and rule.keyword and rule.keyword in text)
                )
            ),
            None,
        )
        if matched is None:
            self.delivery_store.record_execution(
                rule_id='', rule_name='', order_id=order_id, item_id=item_id, buyer_id=buyer_id,
                status='skipped', message='no matching rule',
            )
            return

        try:
            await executor.send_chat_and_ship(
                order_id=order_id,
                item_id=item_id,
                buyer_id=buyer_id,
                delivery_text=matched.delivery_text,
            )
            self.delivery_store.record_execution(
                rule_id=matched.id, rule_name=matched.name, order_id=order_id, item_id=item_id,
                buyer_id=buyer_id, status='success', message='delivered',
            )
        except Exception as exc:
            self.delivery_store.record_execution(
                rule_id=matched.id, rule_name=matched.name, order_id=order_id, item_id=item_id,
                buyer_id=buyer_id, status='failed', message=str(exc),
            )
            raise
```

- [ ] **Step 6: Wire the runtime into `XianyuService` with a small executor adapter**

```python
async def _execute_delivery_action(self, *, order_id: str, item_id: str, buyer_id: str, delivery_text: str) -> str:
    if delivery_text:
        conversation = await self.create_chat_session(peer_user_id=buyer_id, item_id=item_id)
        cid = str(conversation.get('cid') or '')
        if cid:
            await self.send_chat_message(cid=cid, text=delivery_text)
    await self.ship_merchant_order(order_id=order_id, trade_text=delivery_text)
    return 'ok'
```

Add a `delivery_runtime` property that builds `XianyuDeliveryRuntime(item_store=self.item_store, delivery_store=self.delivery_store)`.

- [ ] **Step 7: Run tests to verify they pass**

Run:
```bash
cd backend && pytest \
  tests/test_xianyu_manage_routes.py \
  tests/test_xianyu_delivery_runtime.py -q
```

Expected: route tests may still fail on missing API routes, but runtime unit test should pass before Task 4.

- [ ] **Step 8: Commit**

```bash
git add backend/app/modules/xianyu/service.py \
  backend/app/modules/xianyu/delivery_runtime.py \
  backend/tests/test_xianyu_manage_routes.py \
  backend/tests/test_xianyu_delivery_runtime.py

git commit -m "feat: add xianyu delivery runtime core"
```

---

### Task 4: Expose `/xianyu/manage/*` API routes

**Files:**
- Modify: `backend/app/api/v1/xianyu.py`
- Modify: `backend/app/modules/xianyu/__init__.py`

- [ ] **Step 1: Use the red tests from Tasks 2–3 as the failing route suite**

Run:
```bash
cd backend && pytest tests/test_xianyu_manage_routes.py -q
```

Expected: route 404 failures.

- [ ] **Step 2: Import the new request/response schemas in the router file**

```python
from app.modules.xianyu import (
    XianyuManageItem,
    XianyuManageItemPage,
    XianyuManageItemUpdateRequest,
    XianyuManageItemSyncPageRequest,
    XianyuManageItemMultiQuantityUpdateRequest,
    XianyuDeliveryRule,
    XianyuDeliveryRuleCreateRequest,
    XianyuDeliveryRuleUpdateRequest,
    XianyuDeliveryExecutionRecord,
    XianyuDeliveryRuntimeStatus,
)
```

- [ ] **Step 3: Add manage item routes**

```python
@router.get('/manage/items', response_model=ApiResponse[XianyuManageItemPage])
async def list_xianyu_manage_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: XianyuService = Depends(get_xianyu_service),
):
    try:
        return ApiResponse(data=service.list_manage_items(page=page, page_size=page_size))
    except Exception as exc:
        logger.error(f'获取闲鱼商品管理列表失败: {exc}')
        return ApiResponse(success=False, error=str(exc))
```

Add corresponding `sync-page`, `sync-all`, `GET /{item_id}`, `PUT /{item_id}`, `DELETE /{item_id}`, and `PUT /{item_id}/multi-quantity-delivery` routes in the same style.

- [ ] **Step 4: Add delivery rule and runtime routes**

```python
@router.get('/manage/delivery-rules', response_model=ApiResponse[list[XianyuDeliveryRule]])
async def list_xianyu_delivery_rules(service: XianyuService = Depends(get_xianyu_service)):
    try:
        return ApiResponse(data=service.list_delivery_rules())
    except Exception as exc:
        logger.error(f'获取自动发货规则失败: {exc}')
        return ApiResponse(success=False, error=str(exc))
```

Also add:
- `POST /manage/delivery-rules`
- `PUT /manage/delivery-rules/{rule_id}`
- `DELETE /manage/delivery-rules/{rule_id}`
- `POST /manage/delivery-rules/{rule_id}/toggle`
- `GET /manage/runtime/status`
- `GET /manage/runtime/executions`

- [ ] **Step 5: Run backend route tests to verify green**

Run:
```bash
cd backend && pytest tests/test_xianyu_manage_routes.py -q
```

Expected: `1 passed` (or more if you expanded the suite).

- [ ] **Step 6: Run the full backend manage subset**

Run:
```bash
cd backend && pytest \
  tests/test_xianyu_manage_item_store.py \
  tests/test_xianyu_delivery_store.py \
  tests/test_xianyu_manage_routes.py \
  tests/test_xianyu_delivery_runtime.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/v1/xianyu.py backend/app/modules/xianyu/__init__.py

git commit -m "feat: add xianyu manage api routes"
```

---

### Task 5: Add frontend test tooling and replace the publish tab with manage

**Files:**
- Modify: `web-vue/package.json`
- Create: `web-vue/vitest.config.ts`
- Create: `web-vue/src/test/setup.ts`
- Create: `web-vue/src/views/xianyu/index.spec.ts`
- Modify: `web-vue/src/views/xianyu/index.vue`
- Create: `web-vue/src/views/xianyu/components/XianyuManagePanel.vue`

- [ ] **Step 1: Add the failing navigation test**

```typescript
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/api/modules/xianyu', () => ({
  getXianyuUserProfile: vi.fn().mockResolvedValue({ data: null }),
}))

import XianyuPage from './index.vue'


describe('Xianyu page tabs', () => {
  it('shows 管理 instead of 发布 in bottom tabs', () => {
    const wrapper = mount(XianyuPage, {
      global: {
        stubs: ['router-view', 'XianyuChatPanel', 'XianyuMonitorPanel', 'XianyuManagePanel'],
      },
    })

    const text = wrapper.text()
    expect(text).toContain('管理')
    expect(text).not.toContain('发布')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd web-vue && pnpm add -D vitest @vue/test-utils jsdom && npx vitest run src/views/xianyu/index.spec.ts
```

Expected: test fails because the tab text still includes `发布` and no test config exists yet.

- [ ] **Step 3: Add Vitest configuration**

```typescript
// web-vue/vitest.config.ts
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

```typescript
// web-vue/src/test/setup.ts
import { config } from '@vue/test-utils'

config.global.stubs = {
  transition: false,
  'router-link': { template: '<a><slot /></a>' },
  'router-view': { template: '<div />' },
}
```

- [ ] **Step 4: Replace `publish` with `manage` in `index.vue` and mount `XianyuManagePanel`**

```typescript
import { Bell, ChatDotRound, Link, Search, Setting } from '@element-plus/icons-vue'
import XianyuManagePanel from './components/XianyuManagePanel.vue'

const bottomTabs = [
  { key: 'search', label: '搜索', hint: '真实搜索', icon: Search },
  { key: 'monitor', label: '监控', hint: '动态提醒', icon: Bell },
  { key: 'manage', label: '管理', hint: '商品与发货', icon: Setting },
  { key: 'chat', label: '聊天', hint: '会话消息', icon: ChatDotRound },
]
```

```vue
<XianyuManagePanel
  v-else-if="activeBottomTab === 'manage'"
  :current-user="xianyuUser"
/>
```

- [ ] **Step 5: Add the manage shell component**

```vue
<script setup lang="ts">
import { computed, ref } from 'vue'
import { Box, DataAnalysis, Van } from '@element-plus/icons-vue'
import type { XianyuUserProfile } from '@/api/modules/xianyu'

defineProps<{ currentUser?: XianyuUserProfile | null }>()

const activeTab = ref<'items' | 'delivery' | 'runtime'>('items')
const tabs = computed(() => [
  { key: 'items', label: '商品管理', icon: Box },
  { key: 'delivery', label: '自动发货', icon: Van },
  { key: 'runtime', label: '运行状态', icon: DataAnalysis },
])
</script>
```

Use temporary placeholders in the template for the three sections in this task; full sub-panels land later.

- [ ] **Step 6: Run the navigation test to verify it passes**

Run:
```bash
cd web-vue && npx vitest run src/views/xianyu/index.spec.ts
```

Expected: `1 passed`.

- [ ] **Step 7: Commit**

```bash
git add web-vue/package.json \
  web-vue/vitest.config.ts \
  web-vue/src/test/setup.ts \
  web-vue/src/views/xianyu/index.spec.ts \
  web-vue/src/views/xianyu/index.vue \
  web-vue/src/views/xianyu/components/XianyuManagePanel.vue

git commit -m "feat: replace xianyu publish tab with manage"
```

---

### Task 6: Add frontend API functions and the manage items panel

**Files:**
- Modify: `web-vue/src/api/modules/xianyu.ts`
- Create: `web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue`
- Modify: `web-vue/src/views/xianyu/components/XianyuManagePanel.vue`
- Create: `web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts`

- [ ] **Step 1: Add the failing manage panel test**

```typescript
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/api/modules/xianyu', () => ({
  listXianyuManageItems: vi.fn().mockResolvedValue({
    data: { items: [], total: 0, page: 1, page_size: 20, has_more: false },
  }),
}))

import XianyuManagePanel from './XianyuManagePanel.vue'


describe('XianyuManagePanel', () => {
  it('shows 商品管理 tab by default', () => {
    const wrapper = mount(XianyuManagePanel)
    expect(wrapper.text()).toContain('商品管理')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd web-vue && npx vitest run src/views/xianyu/components/XianyuManagePanel.spec.ts
```

Expected: failure because the child panel and new API bindings are not complete.

- [ ] **Step 3: Add manage item API types and functions**

```typescript
export interface XianyuManageItem {
  item_id: string
  item_title: string
  item_price: string
  item_image: string
  item_status: string
  item_detail: string
  multi_quantity_delivery: boolean
  synced_at: number
  updated_at: number
}

export interface XianyuManageItemPage {
  items: XianyuManageItem[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export function listXianyuManageItems(params?: { page?: number; page_size?: number }) {
  return request.get<ApiResponse<XianyuManageItemPage>>('/xianyu/manage/items', params)
}

export function syncXianyuManageItemsPage(payload: { page: number; page_size: number }) {
  return request.post<ApiResponse<XianyuManageItemPage>>('/xianyu/manage/items/sync-page', payload)
}
```

Also add `syncXianyuManageItemsAll`, `getXianyuManageItem`, `updateXianyuManageItem`, `deleteXianyuManageItem`, and `setXianyuManageItemMultiQuantityDelivery`.

- [ ] **Step 4: Implement `XianyuManageItemsPanel.vue`**

```vue
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listXianyuManageItems,
  syncXianyuManageItemsAll,
  syncXianyuManageItemsPage,
  updateXianyuManageItem,
  setXianyuManageItemMultiQuantityDelivery,
  type XianyuManageItem,
} from '@/api/modules/xianyu'

const loading = ref(false)
const items = ref<XianyuManageItem[]>([])
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
```

Template requirements:
- summary stats row
- sync current page button
- sync all button
- item list cards/table
- edit detail dialog
- multi quantity switch

- [ ] **Step 5: Plug the new items panel into `XianyuManagePanel.vue`**

```vue
<XianyuManageItemsPanel v-if="activeTab === 'items'" />
```

Keep temporary placeholders for `delivery` and `runtime` until the next task.

- [ ] **Step 6: Run tests to verify green**

Run:
```bash
cd web-vue && npx vitest run \
  src/views/xianyu/index.spec.ts \
  src/views/xianyu/components/XianyuManagePanel.spec.ts
```

Expected: both tests pass.

- [ ] **Step 7: Commit**

```bash
git add web-vue/src/api/modules/xianyu.ts \
  web-vue/src/views/xianyu/components/XianyuManagePanel.vue \
  web-vue/src/views/xianyu/components/XianyuManageItemsPanel.vue \
  web-vue/src/views/xianyu/components/XianyuManagePanel.spec.ts

git commit -m "feat: add xianyu manage items panel"
```

---

### Task 7: Add delivery rules panel and runtime panel

**Files:**
- Create: `web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.vue`
- Create: `web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.vue`
- Modify: `web-vue/src/views/xianyu/components/XianyuManagePanel.vue`
- Modify: `web-vue/src/api/modules/xianyu.ts`

- [ ] **Step 1: Add delivery/runtime API functions in red-green order**

First declare the types/functions expected by the components:

```typescript
export interface XianyuDeliveryRule {
  id: string
  name: string
  enabled: boolean
  item_id: string
  keyword: string
  match_mode: string
  delivery_text: string
  send_chat_text: boolean
  send_dummy_ship: boolean
  created_at: number
  updated_at: number
}

export interface XianyuDeliveryExecutionRecord {
  id: string
  rule_id: string
  rule_name: string
  order_id: string
  item_id: string
  buyer_id: string
  status: string
  message: string
  created_at: number
}

export interface XianyuDeliveryRuntimeStatus {
  running: boolean
  last_event_at: number
  last_success_at: number
  last_failure_at: number
  last_error: string
  enabled_rule_count: number
  recent_success_count: number
  recent_failure_count: number
}
```

And add `listXianyuDeliveryRules`, `createXianyuDeliveryRule`, `updateXianyuDeliveryRule`, `deleteXianyuDeliveryRule`, `toggleXianyuDeliveryRule`, `getXianyuDeliveryRuntimeStatus`, and `listXianyuDeliveryExecutions`.

- [ ] **Step 2: Implement `XianyuManageDeliveryPanel.vue` minimally**

```vue
<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listXianyuDeliveryRules,
  createXianyuDeliveryRule,
  updateXianyuDeliveryRule,
  deleteXianyuDeliveryRule,
  toggleXianyuDeliveryRule,
  type XianyuDeliveryRule,
} from '@/api/modules/xianyu'

const loading = ref(false)
const dialogVisible = ref(false)
const editingRuleId = ref('')
const rules = ref<XianyuDeliveryRule[]>([])
const form = reactive({
  name: '',
  enabled: true,
  item_id: '',
  keyword: '',
  match_mode: 'item_id',
  delivery_text: '',
  send_chat_text: true,
  send_dummy_ship: true,
})
</script>
```

Template requirements:
- stats summary
- create/edit dialog
- rule cards or table
- toggle/delete buttons

- [ ] **Step 3: Implement `XianyuManageRuntimePanel.vue` minimally**

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  getXianyuDeliveryRuntimeStatus,
  listXianyuDeliveryExecutions,
  type XianyuDeliveryExecutionRecord,
  type XianyuDeliveryRuntimeStatus,
} from '@/api/modules/xianyu'

const loading = ref(false)
const status = ref<XianyuDeliveryRuntimeStatus | null>(null)
const records = ref<XianyuDeliveryExecutionRecord[]>([])
</script>
```

Template requirements:
- runtime stats cards
- last error section
- recent execution list with success/failed/skipped badge
- refresh button

- [ ] **Step 4: Mount both panels inside `XianyuManagePanel.vue`**

```vue
<XianyuManageDeliveryPanel v-else-if="activeTab === 'delivery'" />
<XianyuManageRuntimePanel v-else />
```

- [ ] **Step 5: Run frontend tests and type check**

Run:
```bash
cd web-vue && npx vitest run src/views/xianyu/index.spec.ts src/views/xianyu/components/XianyuManagePanel.spec.ts
pnpm exec vue-tsc --noEmit
```

Expected: tests pass and type check succeeds.

- [ ] **Step 6: Commit**

```bash
git add web-vue/src/api/modules/xianyu.ts \
  web-vue/src/views/xianyu/components/XianyuManagePanel.vue \
  web-vue/src/views/xianyu/components/XianyuManageDeliveryPanel.vue \
  web-vue/src/views/xianyu/components/XianyuManageRuntimePanel.vue

git commit -m "feat: add xianyu delivery and runtime panels"
```

---

### Task 8: Integrate the minimal runtime loop with current Xianyu event flow and verify end-to-end

**Files:**
- Modify: `backend/app/modules/xianyu/service.py`
- Modify: `backend/app/modules/xianyu/delivery_runtime.py`
- Modify: `backend/tests/test_xianyu_delivery_runtime.py`
- Optionally modify: `backend/tests/test_xianyu_chat_ai_background_listener.py`

- [ ] **Step 1: Add a failing integration-style runtime test around service event forwarding**

```python
import asyncio

from app.modules.xianyu.service import XianyuService


def test_service_forwards_candidate_delivery_event_to_runtime(monkeypatch, tmp_path):
    service = XianyuService()
    service._item_store_path = tmp_path / 'items.json'
    service._delivery_rules_path = tmp_path / 'rules.json'
    service._delivery_runtime_path = tmp_path / 'runtime.json'
    service._item_store = None
    service._delivery_store = None

    captured = {}

    async def fake_process_event(event, executor):
        captured['event'] = event

    monkeypatch.setattr(service.delivery_runtime, 'process_event', fake_process_event)

    asyncio.run(service.handle_delivery_candidate_event({
        'order_id': 'order-1',
        'item_id': '1001',
        'buyer_id': 'buyer-1',
        'text': '我已付款，等待发货',
    }))

    assert captured['event']['order_id'] == 'order-1'
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd backend && pytest tests/test_xianyu_delivery_runtime.py -q
```

Expected: missing `handle_delivery_candidate_event` or equivalent.

- [ ] **Step 3: Add a thin service entrypoint and call it from the existing chat listener path**

```python
@property
def delivery_runtime(self) -> XianyuDeliveryRuntime:
    if self._delivery_runtime is None:
        self._delivery_runtime = XianyuDeliveryRuntime(item_store=self.item_store, delivery_store=self.delivery_store)
    return self._delivery_runtime


async def handle_delivery_candidate_event(self, payload: dict[str, Any]) -> None:
    await self.delivery_runtime.process_event(payload, executor=self)
```

Inside the existing background listener path, after decoding a candidate paid-order / shipped-order event, forward the normalized event to `handle_delivery_candidate_event(...)`.

- [ ] **Step 4: Make `XianyuService` satisfy the runtime executor contract**

```python
async def send_chat_and_ship(self, *, order_id: str, item_id: str, buyer_id: str, delivery_text: str) -> str:
    return await self._execute_delivery_action(
        order_id=order_id,
        item_id=item_id,
        buyer_id=buyer_id,
        delivery_text=delivery_text,
    )
```

- [ ] **Step 5: Run the backend manage subset and one broader regression check**

Run:
```bash
cd backend && pytest \
  tests/test_xianyu_manage_item_store.py \
  tests/test_xianyu_delivery_store.py \
  tests/test_xianyu_manage_routes.py \
  tests/test_xianyu_delivery_runtime.py \
  tests/test_xianyu_chat_ai_background_listener.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 6: Run final frontend verification**

Run:
```bash
cd web-vue && npx vitest run src/views/xianyu/index.spec.ts src/views/xianyu/components/XianyuManagePanel.spec.ts
pnpm exec vue-tsc --noEmit
pnpm build
```

Expected: tests pass, type check passes, and the Vite build succeeds.

- [ ] **Step 7: Commit**

```bash
git add backend/app/modules/xianyu/service.py \
  backend/app/modules/xianyu/delivery_runtime.py \
  backend/tests/test_xianyu_delivery_runtime.py

git commit -m "feat: wire xianyu auto delivery runtime into service events"
```

---

## Self-Review

### Spec coverage check
- Navigation replacement (`publish` -> `manage`): covered in Task 5.
- Manage tab shell + three sub-panels: covered in Tasks 5–7.
- Item management APIs + UI: covered in Tasks 1, 2, 4, 6.
- Delivery rule CRUD + UI: covered in Tasks 1, 3, 4, 7.
- Runtime status + execution records: covered in Tasks 1, 3, 4, 7.
- Minimal auto-delivery execution loop integrated with current Xianyu flow: covered in Task 8.
- Tests and verification: covered in every task plus Task 8 final verification.

### Placeholder scan
This plan avoids `TODO`, `TBD`, and “write tests later” placeholders. Where behavior is staged (e.g. richer matching), it is explicitly deferred outside V1 rather than left ambiguous.

### Type consistency
The new names are consistent throughout the plan:
- `XianyuManageItem*`
- `XianyuDeliveryRule*`
- `XianyuDeliveryExecutionRecord`
- `XianyuDeliveryRuntimeStatus`
- `XianyuItemStore`
- `XianyuDeliveryStore`
- `XianyuDeliveryRuntime`

