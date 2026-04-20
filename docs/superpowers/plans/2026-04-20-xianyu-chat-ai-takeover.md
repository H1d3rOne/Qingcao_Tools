# Xianyu Chat AI Takeover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给本项目闲鱼聊天模块接入“页面在线时生效”的 AI 自动回复，并补齐全局开关、会话级开关、AI 配置弹窗与后端 `chat/completions` 编排。

**Architecture:** 后端沿用现有闲鱼真实聊天链路，在 `service.py` 周边新增一个小型 `ai_store.py` 负责 AI 配置与会话状态持久化，再由 `service.py` 负责模型请求、消息去重和触发判断；前端继续以 `XianyuChatPanel.vue` 为主入口，在左侧顶部账号行增加 AI 控件，并通过新的 AI 配置接口和会话状态接口驱动 UI。

**Tech Stack:** FastAPI, Pydantic, httpx, asyncio, Vue 3, TypeScript, Element Plus

---

## File Structure

### Backend

- Create: `backend/app/modules/xianyu/ai_store.py`
  - 只负责 AI 配置和会话 AI 状态的 JSON 持久化，避免继续堆大 `service.py`
- Modify: `backend/app/modules/xianyu/schemas.py`
  - 新增 AI 配置、会话状态、测试回复相关 Schema
- Modify: `backend/app/modules/xianyu/__init__.py`
  - 导出新 Schema
- Modify: `backend/app/modules/xianyu/service.py`
  - 读取/保存配置、调用 `chat/completions`、处理推送触发与去重
- Modify: `backend/app/api/v1/xianyu.py`
  - 新增 AI 配置、会话状态、测试回复接口，并在聊天 WebSocket 代理中接入自动回复分支
- Create: `backend/tests/test_xianyu_chat_ai_store.py`
- Create: `backend/tests/test_xianyu_chat_ai_api.py`
- Create: `backend/tests/test_xianyu_chat_ai_trigger.py`
- Create: `backend/tests/test_xianyu_chat_ai_routes.py`
- Create: `backend/tests/test_xianyu_chat_ai_ws.py`

### Frontend

- Modify: `web-vue/src/api/modules/xianyu.ts`
  - 新增 AI 配置、会话状态、测试回复相关类型与请求函数
- Create: `web-vue/src/views/xianyu/components/XianyuChatAiConfigDialog.vue`
  - AI 配置弹窗
- Modify: `web-vue/src/views/xianyu/components/XianyuChatPanel.vue`
  - 左侧顶部账号行加入 AI 总开关 / 当前会话 AI 开关 / AI 配置按钮；左侧会话项增加 AI 状态标记

### Config Artifacts

- Create at runtime: `backend/config/xianyu_ai_config.json`
- Create at runtime: `backend/config/xianyu_ai_sessions.json`

### Verification Notes

- 后端以 `pytest` 为主，先写失败测试再实现
- 前端当前没有现成的单元测试基建，本计划不额外引入 Vitest；前端改动用 `vue-tsc --noEmit`、`eslint` 和浏览器手工验证兜底

---

### Task 1: Add AI schemas and a dedicated JSON store

**Files:**
- Create: `backend/app/modules/xianyu/ai_store.py`
- Modify: `backend/app/modules/xianyu/schemas.py`
- Modify: `backend/app/modules/xianyu/__init__.py`
- Test: `backend/tests/test_xianyu_chat_ai_store.py`

- [ ] **Step 1: Write the failing store tests**

```python
from pathlib import Path

from app.modules.xianyu.ai_store import XianyuChatAiStore
from app.modules.xianyu.schemas import XianyuChatAiConfigUpdateRequest


def test_ai_store_loads_defaults_and_masks_missing_key(tmp_path: Path):
    store = XianyuChatAiStore(
        config_path=tmp_path / 'xianyu_ai_config.json',
        sessions_path=tmp_path / 'xianyu_ai_sessions.json',
    )

    config = store.load_config()

    assert config.enabled is False
    assert config.base_url == 'https://api.openai.com/v1'
    assert config.model == 'gpt-4.1-mini'
    assert config.api_key_configured is False
    assert config.api_key_masked == ''


def test_ai_store_preserves_existing_api_key_when_update_omits_new_value(tmp_path: Path):
    store = XianyuChatAiStore(
        config_path=tmp_path / 'xianyu_ai_config.json',
        sessions_path=tmp_path / 'xianyu_ai_sessions.json',
    )
    store.save_config(
        XianyuChatAiConfigUpdateRequest(
            enabled=True,
            base_url='https://example.com/v1',
            api_key='sk-test-12345678',
            model='gpt-4.1-mini',
            system_prompt='reply briefly',
            temperature=0.3,
        )
    )

    config = store.save_config(
        XianyuChatAiConfigUpdateRequest(
            enabled=False,
            base_url='https://example.com/v1',
            api_key='',
            model='gpt-4.1-mini',
            system_prompt='reply briefly',
            temperature=0.2,
        )
    )

    assert config.enabled is False
    assert config.api_key_configured is True
    assert config.api_key_masked.endswith('5678')
    assert store.load_secret_api_key() == 'sk-test-12345678'


def test_ai_store_roundtrips_session_states(tmp_path: Path):
    store = XianyuChatAiStore(
        config_path=tmp_path / 'xianyu_ai_config.json',
        sessions_path=tmp_path / 'xianyu_ai_sessions.json',
    )

    store.set_session_enabled('cid-1', True)
    store.set_session_enabled('cid-2', False)

    assert store.get_session_enabled('cid-1') is True
    assert store.get_session_enabled('cid-2') is False
    assert [item.model_dump() for item in store.list_session_states(['cid-1', 'cid-2'])] == [
        {'cid': 'cid-1', 'enabled': True},
        {'cid': 'cid-2', 'enabled': False},
    ]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_chat_ai_store.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.xianyu.ai_store'` and/or missing AI schemas.

- [ ] **Step 3: Add the new AI schemas**

Update `backend/app/modules/xianyu/schemas.py` with:

```python
class XianyuChatAiConfig(BaseModel):
    enabled: bool = Field(False, description='是否启用 AI 总开关')
    base_url: str = Field('https://api.openai.com/v1', description='OpenAI 兼容接口根地址')
    model: str = Field('gpt-4.1-mini', description='模型名称')
    system_prompt: str = Field('你是闲鱼客服助手，回复要简洁、礼貌、像真人卖家。', description='系统提示词')
    temperature: float = Field(0.3, ge=0, le=2, description='采样温度')
    api_key_configured: bool = Field(False, description='是否已配置 API Key')
    api_key_masked: str = Field('', description='脱敏后的 API Key')


class XianyuChatAiConfigUpdateRequest(BaseModel):
    enabled: bool = Field(False, description='是否启用 AI 总开关')
    base_url: str = Field(..., min_length=1, description='OpenAI 兼容接口根地址')
    api_key: str = Field('', description='新的 API Key，可为空表示保留旧值')
    model: str = Field(..., min_length=1, description='模型名称')
    system_prompt: str = Field(..., min_length=1, description='系统提示词')
    temperature: float = Field(0.3, ge=0, le=2, description='采样温度')


class XianyuChatAiSessionState(BaseModel):
    cid: str = Field(..., min_length=1, description='会话 CID')
    enabled: bool = Field(False, description='当前会话是否启用 AI')


class XianyuChatAiSessionUpdateRequest(BaseModel):
    enabled: bool = Field(False, description='当前会话是否启用 AI')


class XianyuChatAiTestRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000, description='测试输入内容')
    cid: str = Field('', description='可选的会话 CID，用于补充上下文')


class XianyuChatAiTestResponse(BaseModel):
    reply: str = Field('', description='模型回复')
```

Also export them from `backend/app/modules/xianyu/__init__.py`.

- [ ] **Step 4: Implement the dedicated store**

Create `backend/app/modules/xianyu/ai_store.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from app.modules.xianyu.schemas import (
    XianyuChatAiConfig,
    XianyuChatAiConfigUpdateRequest,
    XianyuChatAiSessionState,
)


class XianyuChatAiStore:
    def __init__(self, config_path: Path, sessions_path: Path):
        self.config_path = Path(config_path)
        self.sessions_path = Path(sessions_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.sessions_path.parent.mkdir(parents=True, exist_ok=True)

    def load_config(self) -> XianyuChatAiConfig:
        payload = self._read_json(self.config_path, {})
        api_key = str(payload.get('api_key') or '')
        return XianyuChatAiConfig(
            enabled=bool(payload.get('enabled', False)),
            base_url=str(payload.get('base_url') or 'https://api.openai.com/v1'),
            model=str(payload.get('model') or 'gpt-4.1-mini'),
            system_prompt=str(payload.get('system_prompt') or '你是闲鱼客服助手，回复要简洁、礼貌、像真人卖家。'),
            temperature=float(payload.get('temperature', 0.3)),
            api_key_configured=bool(api_key),
            api_key_masked=self._mask_api_key(api_key),
        )

    def load_secret_api_key(self) -> str:
        payload = self._read_json(self.config_path, {})
        return str(payload.get('api_key') or '')

    def save_config(self, request: XianyuChatAiConfigUpdateRequest) -> XianyuChatAiConfig:
        current = self._read_json(self.config_path, {})
        next_api_key = request.api_key.strip() or str(current.get('api_key') or '')
        payload = {
            'enabled': request.enabled,
            'base_url': request.base_url.strip().rstrip('/'),
            'api_key': next_api_key,
            'model': request.model.strip(),
            'system_prompt': request.system_prompt.strip(),
            'temperature': request.temperature,
        }
        self._write_json(self.config_path, payload)
        return self.load_config()

    def get_session_enabled(self, cid: str) -> bool:
        payload = self._read_json(self.sessions_path, {'sessions': {}})
        return bool((payload.get('sessions') or {}).get(cid, False))

    def set_session_enabled(self, cid: str, enabled: bool) -> XianyuChatAiSessionState:
        payload = self._read_json(self.sessions_path, {'sessions': {}})
        sessions = dict(payload.get('sessions') or {})
        sessions[cid] = enabled
        self._write_json(self.sessions_path, {'sessions': sessions})
        return XianyuChatAiSessionState(cid=cid, enabled=enabled)

    def list_session_states(self, cids: list[str]) -> list[XianyuChatAiSessionState]:
        payload = self._read_json(self.sessions_path, {'sessions': {}})
        sessions = dict(payload.get('sessions') or {})
        return [XianyuChatAiSessionState(cid=cid, enabled=bool(sessions.get(cid, False))) for cid in cids]
```

- [ ] **Step 5: Run the store tests again**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_chat_ai_store.py -q
```

Expected: PASS (`3 passed`).

- [ ] **Step 6: Commit the store layer**

```bash
git add backend/app/modules/xianyu/ai_store.py backend/app/modules/xianyu/schemas.py backend/app/modules/xianyu/__init__.py backend/tests/test_xianyu_chat_ai_store.py
git commit -m "feat: add xianyu chat ai config store"
```

---

### Task 2: Add the OpenAI-compatible AI client in the service layer

**Files:**
- Modify: `backend/app/modules/xianyu/service.py`
- Test: `backend/tests/test_xianyu_chat_ai_api.py`

- [ ] **Step 1: Write the failing AI API tests**

```python
import httpx
import pytest

from app.modules.xianyu.schemas import XianyuChatAiConfig
from app.modules.xianyu.service import XianyuService


@pytest.mark.asyncio
async def test_request_chat_ai_reply_posts_chat_completions(monkeypatch):
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured['url'] = str(request.url)
        captured['auth'] = request.headers.get('Authorization')
        captured['payload'] = (await request.aread()).decode()
        return httpx.Response(
            200,
            json={
                'choices': [
                    {
                        'message': {
                            'content': '在的，还可以拍。'
                        }
                    }
                ]
            },
        )

    service = XianyuService()
    config = XianyuChatAiConfig(
        enabled=True,
        base_url='https://example.com/v1',
        model='gpt-4.1-mini',
        system_prompt='reply briefly',
        temperature=0.3,
        api_key_configured=True,
        api_key_masked='sk-****5678',
    )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(service, '_load_secret_chat_ai_api_key', lambda: 'sk-test-12345678')

    reply = await service._request_chat_ai_reply(
        config=config,
        messages=[{'role': 'user', 'content': '这个还在吗？'}],
        transport=transport,
    )

    assert reply == '在的，还可以拍。'
    assert captured['url'] == 'https://example.com/v1/chat/completions'
    assert captured['auth'] == 'Bearer sk-test-12345678'
    assert '这个还在吗？' in captured['payload']


@pytest.mark.asyncio
async def test_request_chat_ai_reply_raises_when_choices_are_missing(monkeypatch):
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={'choices': []})

    service = XianyuService()
    config = XianyuChatAiConfig(
        enabled=True,
        base_url='https://example.com/v1',
        model='gpt-4.1-mini',
        system_prompt='reply briefly',
        temperature=0.3,
        api_key_configured=True,
        api_key_masked='sk-****5678',
    )
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(service, '_load_secret_chat_ai_api_key', lambda: 'sk-test-12345678')

    with pytest.raises(ValueError, match='AI 接口未返回可用回复'):
        await service._request_chat_ai_reply(config=config, messages=[{'role': 'user', 'content': 'hi'}], transport=transport)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_chat_ai_api.py -q
```

Expected: FAIL with missing `_request_chat_ai_reply` and `_load_secret_chat_ai_api_key`.

- [ ] **Step 3: Wire the store into `XianyuService`**

Update the constructor and add helpers in `backend/app/modules/xianyu/service.py`:

```python
from collections import deque

from app.modules.xianyu.ai_store import XianyuChatAiStore
from app.modules.xianyu.schemas import XianyuChatAiConfig, XianyuChatAiConfigUpdateRequest


class XianyuService:
    def __init__(self):
        self._chat_ai_config_path = Path.cwd() / 'config' / 'xianyu_ai_config.json'
        self._chat_ai_sessions_path = Path.cwd() / 'config' / 'xianyu_ai_sessions.json'
        self._chat_ai_store: XianyuChatAiStore | None = None
        self._processed_ai_message_keys = deque(maxlen=1000)
        self._processed_ai_message_set: set[str] = set()
        ...

    @property
    def chat_ai_store(self) -> XianyuChatAiStore:
        if self._chat_ai_store is None:
            self._chat_ai_store = XianyuChatAiStore(
                config_path=self._chat_ai_config_path,
                sessions_path=self._chat_ai_sessions_path,
            )
        return self._chat_ai_store

    def get_chat_ai_config(self) -> XianyuChatAiConfig:
        return self.chat_ai_store.load_config()

    def update_chat_ai_config(self, request: XianyuChatAiConfigUpdateRequest) -> XianyuChatAiConfig:
        return self.chat_ai_store.save_config(request)

    def _load_secret_chat_ai_api_key(self) -> str:
        return self.chat_ai_store.load_secret_api_key().strip()
```

- [ ] **Step 4: Implement the OpenAI-compatible request helper**

Add this method to `backend/app/modules/xianyu/service.py`:

```python
async def _request_chat_ai_reply(
    self,
    *,
    config: XianyuChatAiConfig,
    messages: list[dict[str, str]],
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    api_key = self._load_secret_chat_ai_api_key()
    if not api_key:
        raise ValueError('AI API Key 未配置')

    base_url = config.base_url.rstrip('/')
    payload = {
        'model': config.model,
        'temperature': config.temperature,
        'messages': messages,
    }
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    async with httpx.AsyncClient(timeout=30.0, transport=transport) as client:
        response = await client.post(f'{base_url}/chat/completions', headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    choices = data.get('choices') or []
    if not choices:
        raise ValueError('AI 接口未返回可用回复')

    message = choices[0].get('message') or {}
    content = str(message.get('content') or '').strip()
    if not content:
        raise ValueError('AI 接口返回了空回复')
    return content
```

- [ ] **Step 5: Run the API tests again**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_chat_ai_api.py -q
```

Expected: PASS (`2 passed`).

- [ ] **Step 6: Commit the AI client layer**

```bash
git add backend/app/modules/xianyu/service.py backend/tests/test_xianyu_chat_ai_api.py
git commit -m "feat: add xianyu chat ai api client"
```

---

### Task 3: Implement AI trigger rules, prompt building, and de-duplication

**Files:**
- Modify: `backend/app/modules/xianyu/service.py`
- Test: `backend/tests/test_xianyu_chat_ai_trigger.py`

- [ ] **Step 1: Write the failing trigger tests**

```python
import pytest

from app.modules.xianyu.schemas import XianyuChatAiConfig, XianyuChatProfile
from app.modules.xianyu.service import XianyuService


@pytest.mark.asyncio
async def test_maybe_auto_reply_from_decoded_push_replies_once_for_enabled_text(monkeypatch):
    service = XianyuService()
    profile = XianyuChatProfile(user_id='111', main_user_id='111', domain='goofish', display_name='卖家', avatar='')

    monkeypatch.setattr(
        service,
        'get_chat_ai_config',
        lambda: XianyuChatAiConfig(
            enabled=True,
            base_url='https://example.com/v1',
            model='gpt-4.1-mini',
            system_prompt='reply briefly',
            temperature=0.3,
            api_key_configured=True,
            api_key_masked='sk-****5678',
        ),
    )
    monkeypatch.setattr(service.chat_ai_store, 'get_session_enabled', lambda cid: cid == 'cid-1')

    sent = {}

    async def fake_request_chat_ai_reply(**kwargs):
        return '在的，现在还在。'

    async def fake_send_chat_text(cid: str, text: str):
        sent['cid'] = cid
        sent['text'] = text
        return None

    monkeypatch.setattr(service, '_request_chat_ai_reply', fake_request_chat_ai_reply)
    monkeypatch.setattr(service, 'send_chat_text', fake_send_chat_text)

    decoded = {
        'type': 'sync',
        'items': [
            {
                'biz_type': 40000,
                'decoded': {
                    'raw_text': 'same-message',
                    'json_objects': [
                        {
                            '1': {
                                '2': 'cid-1@goofish',
                                '10': {
                                    'senderUserId': '222',
                                    'reminderContent': '这个还在吗？',
                                    'reminderTitle': '买家A',
                                },
                            }
                        }
                    ],
                },
            }
        ],
    }

    reply = await service.maybe_auto_reply_from_decoded_push(profile, decoded)
    duplicate_reply = await service.maybe_auto_reply_from_decoded_push(profile, decoded)

    assert reply == '在的，现在还在。'
    assert duplicate_reply is None
    assert sent == {'cid': 'cid-1', 'text': '在的，现在还在。'}


@pytest.mark.asyncio
async def test_maybe_auto_reply_from_decoded_push_skips_when_global_or_session_disabled(monkeypatch):
    service = XianyuService()
    profile = XianyuChatProfile(user_id='111', main_user_id='111', domain='goofish', display_name='卖家', avatar='')

    monkeypatch.setattr(
        service,
        'get_chat_ai_config',
        lambda: XianyuChatAiConfig(
            enabled=False,
            base_url='https://example.com/v1',
            model='gpt-4.1-mini',
            system_prompt='reply briefly',
            temperature=0.3,
            api_key_configured=True,
            api_key_masked='sk-****5678',
        ),
    )

    decoded = {
        'type': 'sync',
        'items': [
            {
                'biz_type': 40000,
                'decoded': {
                    'raw_text': 'msg-2',
                    'json_objects': [
                        {'1': {'2': 'cid-2@goofish', '10': {'senderUserId': '222', 'reminderContent': 'hi'}}}
                    ],
                },
            }
        ],
    }

    assert await service.maybe_auto_reply_from_decoded_push(profile, decoded) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_chat_ai_trigger.py -q
```

Expected: FAIL with missing `maybe_auto_reply_from_decoded_push`.

- [ ] **Step 3: Add message extraction and de-dup helpers**

In `backend/app/modules/xianyu/service.py`, add helpers with these signatures:

```python
def _extract_ai_candidate(self, item: dict[str, Any]) -> dict[str, str] | None:
    decoded = item.get('decoded') or {}
    if item.get('biz_type') != 40000:
        return None

    for obj in decoded.get('json_objects') or []:
        payload = obj.get('1') or {}
        meta = payload.get('10') or {}
        cid = str(payload.get('2') or '').split('@')[0].strip()
        sender_uid = str(meta.get('senderUserId') or '').strip()
        text = str(meta.get('reminderContent') or '').strip()
        if cid and sender_uid and text:
            raw_text = str(decoded.get('raw_text') or '')
            key = hashlib.sha1(raw_text.encode('utf-8', errors='ignore')).hexdigest()
            return {'cid': cid, 'sender_uid': sender_uid, 'text': text, 'message_key': key}
    return None


def _remember_ai_message_key(self, key: str) -> bool:
    if key in self._processed_ai_message_set:
        return False
    if len(self._processed_ai_message_keys) == self._processed_ai_message_keys.maxlen:
        dropped = self._processed_ai_message_keys.popleft()
        self._processed_ai_message_set.discard(dropped)
    self._processed_ai_message_keys.append(key)
    self._processed_ai_message_set.add(key)
    return True
```

- [ ] **Step 4: Add prompt building and orchestration**

Implement the main method in `backend/app/modules/xianyu/service.py`:

```python
def _build_chat_ai_messages(self, *, config: XianyuChatAiConfig, text: str, cid: str = '') -> list[dict[str, str]]:
    content = text if not cid else f'会话 CID：{cid}
买家消息：{text}'
    return [
        {'role': 'system', 'content': config.system_prompt},
        {'role': 'user', 'content': content},
    ]


async def maybe_auto_reply_from_decoded_push(self, profile: XianyuChatProfile, decoded: dict[str, Any]) -> str | None:
    if decoded.get('type') != 'sync':
        return None

    config = self.get_chat_ai_config()
    if not config.enabled:
        return None

    current_user_id = profile.main_user_id or profile.user_id
    for item in decoded.get('items') or []:
        candidate = self._extract_ai_candidate(item)
        if not candidate:
            continue
        if candidate['sender_uid'] == current_user_id:
            continue
        if not self.chat_ai_store.get_session_enabled(candidate['cid']):
            continue
        if not self._remember_ai_message_key(candidate['message_key']):
            continue

        messages = self._build_chat_ai_messages(config=config, text=candidate['text'], cid=candidate['cid'])
        reply = await self._request_chat_ai_reply(config=config, messages=messages)
        await self.send_chat_text(cid=candidate['cid'], text=reply)
        return reply

    return None
```

- [ ] **Step 5: Run the trigger tests again**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_chat_ai_trigger.py -q
```

Expected: PASS (`2 passed`).

- [ ] **Step 6: Commit the trigger layer**

```bash
git add backend/app/modules/xianyu/service.py backend/tests/test_xianyu_chat_ai_trigger.py
git commit -m "feat: add xianyu chat ai trigger flow"
```

---

### Task 4: Wire AI auto-reply into the existing chat WebSocket proxy

**Files:**
- Modify: `backend/app/api/v1/xianyu.py`
- Test: `backend/tests/test_xianyu_chat_ai_ws.py`

- [ ] **Step 1: Write the failing WebSocket integration test**

```python
import asyncio
from fastapi.testclient import TestClient

from app.api.deps import get_xianyu_service
from app.main import app
from app.modules.xianyu.schemas import XianyuChatProfile


class FakeChatClient:
    def __init__(self):
        self.profile = XianyuChatProfile(user_id='111', main_user_id='111', domain='goofish', display_name='卖家', avatar='')
        self._queue = asyncio.Queue()
        self._queue.put_nowait({'lwp': '/s/sync', 'headers': {}, 'body': {'syncPushPackage': {'data': []}}})

    async def next_push(self):
        return await self._queue.get()

    async def close(self):
        return None


class FakeService:
    def __init__(self):
        self.ai_called = 0

    async def open_chat_ws_client(self):
        return FakeChatClient()

    def decode_chat_push(self, payload):
        return {'type': 'sync', 'items': []}

    async def maybe_auto_reply_from_decoded_push(self, profile, decoded):
        self.ai_called += 1
        return None



def test_xianyu_chat_ws_invokes_ai_handler_for_pushes():
    fake_service = FakeService()
    app.dependency_overrides[get_xianyu_service] = lambda: fake_service

    client = TestClient(app)
    with client.websocket_connect('/api/v1/xianyu/chat/ws') as websocket:
        connected = websocket.receive_json()
        pushed = websocket.receive_json()
        assert connected['type'] == 'connected'
        assert pushed['type'] == 'push'

    assert fake_service.ai_called == 1
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_chat_ai_ws.py -q
```

Expected: FAIL because the WebSocket route does not call `maybe_auto_reply_from_decoded_push`.

- [ ] **Step 3: Call the AI orchestrator from the relay loop**

Update `backend/app/api/v1/xianyu.py` inside `relay_pushes()`:

```python
async def relay_pushes():
    while True:
        payload = await chat_client.next_push()
        decoded = service.decode_chat_push(payload)
        await websocket.send_json(
            {
                'type': 'push',
                'lwp': payload.get('lwp'),
                'headers': payload.get('headers'),
                'body': payload.get('body'),
                'decoded': decoded,
            }
        )
        try:
            await service.maybe_auto_reply_from_decoded_push(chat_client.profile, decoded)
        except Exception as exc:
            logger.warning(f'闲鱼聊天 AI 自动回复失败: {exc}')
```

Important: keep the `send_json` before the AI call so the page remains responsive even when the model is slow.

- [ ] **Step 4: Run the WebSocket test again**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_chat_ai_ws.py -q
```

Expected: PASS (`1 passed`).

- [ ] **Step 5: Commit the WebSocket integration**

```bash
git add backend/app/api/v1/xianyu.py backend/tests/test_xianyu_chat_ai_ws.py
git commit -m "feat: trigger xianyu chat ai from websocket proxy"
```

---

### Task 5: Expose AI config, session-state, and test-reply APIs

**Files:**
- Modify: `backend/app/api/v1/xianyu.py`
- Test: `backend/tests/test_xianyu_chat_ai_routes.py`

- [ ] **Step 1: Write the failing route tests**

```python
from fastapi.testclient import TestClient

from app.api.deps import get_xianyu_service
from app.main import app


class FakeXianyuAiService:
    def get_chat_ai_config(self):
        return {
            'enabled': True,
            'base_url': 'https://example.com/v1',
            'model': 'gpt-4.1-mini',
            'system_prompt': 'reply briefly',
            'temperature': 0.3,
            'api_key_configured': True,
            'api_key_masked': 'sk-****5678',
        }

    def update_chat_ai_config(self, request):
        return self.get_chat_ai_config()

    def list_chat_ai_session_states(self, cids=None):
        return [{'cid': 'cid-1', 'enabled': True}]

    def set_chat_ai_session_state(self, cid: str, enabled: bool):
        return {'cid': cid, 'enabled': enabled}

    async def test_chat_ai_reply(self, text: str, cid: str = ''):
        return '在的，还可以拍。'



def test_xianyu_chat_ai_routes_roundtrip():
    fake_service = FakeXianyuAiService()
    app.dependency_overrides[get_xianyu_service] = lambda: fake_service
    client = TestClient(app)

    config_resp = client.get('/api/v1/xianyu/chat/ai/config')
    assert config_resp.status_code == 200
    assert config_resp.json()['data']['enabled'] is True

    update_resp = client.post('/api/v1/xianyu/chat/ai/config', json={
        'enabled': True,
        'base_url': 'https://example.com/v1',
        'api_key': '',
        'model': 'gpt-4.1-mini',
        'system_prompt': 'reply briefly',
        'temperature': 0.3,
    })
    assert update_resp.status_code == 200

    sessions_resp = client.get('/api/v1/xianyu/chat/ai/sessions', params=[('cid', 'cid-1')])
    assert sessions_resp.status_code == 200
    assert sessions_resp.json()['data'][0]['cid'] == 'cid-1'

    toggle_resp = client.post('/api/v1/xianyu/chat/ai/sessions/cid-1', json={'enabled': True})
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()['data']['enabled'] is True

    test_resp = client.post('/api/v1/xianyu/chat/ai/test', json={'text': '你好', 'cid': 'cid-1'})
    assert test_resp.status_code == 200
    assert test_resp.json()['data']['reply'] == '在的，还可以拍。'

    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the route tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_chat_ai_routes.py -q
```

Expected: FAIL with 404s for the new AI routes.

- [ ] **Step 3: Add service helpers for routes**

In `backend/app/modules/xianyu/service.py`, add:

```python
def list_chat_ai_session_states(self, cids: list[str]) -> list[XianyuChatAiSessionState]:
    return self.chat_ai_store.list_session_states(cids)


def set_chat_ai_session_state(self, cid: str, enabled: bool) -> XianyuChatAiSessionState:
    return self.chat_ai_store.set_session_enabled(cid, enabled)


async def test_chat_ai_reply(self, text: str, cid: str = '') -> str:
    config = self.get_chat_ai_config()
    messages = self._build_chat_ai_messages(config=config, text=text, cid=cid)
    return await self._request_chat_ai_reply(config=config, messages=messages)
```

- [ ] **Step 4: Add the FastAPI routes**

Update `backend/app/api/v1/xianyu.py` with:

```python
@router.get('/chat/ai/config', response_model=ApiResponse[XianyuChatAiConfig])
async def get_xianyu_chat_ai_config(service: XianyuService = Depends(get_xianyu_service)):
    return ApiResponse(data=service.get_chat_ai_config())


@router.post('/chat/ai/config', response_model=ApiResponse[XianyuChatAiConfig])
async def update_xianyu_chat_ai_config(
    request: XianyuChatAiConfigUpdateRequest,
    service: XianyuService = Depends(get_xianyu_service),
):
    return ApiResponse(data=service.update_chat_ai_config(request))


@router.get('/chat/ai/sessions', response_model=ApiResponse[list[XianyuChatAiSessionState]])
async def list_xianyu_chat_ai_sessions(
    cid: list[str] = Query(default_factory=list),
    service: XianyuService = Depends(get_xianyu_service),
):
    return ApiResponse(data=service.list_chat_ai_session_states(cid))


@router.post('/chat/ai/sessions/{cid}', response_model=ApiResponse[XianyuChatAiSessionState])
async def update_xianyu_chat_ai_session(
    cid: str,
    request: XianyuChatAiSessionUpdateRequest,
    service: XianyuService = Depends(get_xianyu_service),
):
    return ApiResponse(data=service.set_chat_ai_session_state(cid, request.enabled))


@router.post('/chat/ai/test', response_model=ApiResponse[XianyuChatAiTestResponse])
async def test_xianyu_chat_ai(
    request: XianyuChatAiTestRequest,
    service: XianyuService = Depends(get_xianyu_service),
):
    reply = await service.test_chat_ai_reply(text=request.text, cid=request.cid)
    return ApiResponse(data=XianyuChatAiTestResponse(reply=reply))
```

- [ ] **Step 5: Run the route tests again**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_chat_ai_routes.py -q
```

Expected: PASS (`1 passed`).

- [ ] **Step 6: Commit the route layer**

```bash
git add backend/app/api/v1/xianyu.py backend/app/modules/xianyu/service.py backend/tests/test_xianyu_chat_ai_routes.py
git commit -m "feat: add xianyu chat ai routes"
```

---

### Task 6: Add frontend API bindings and the AI config dialog

**Files:**
- Modify: `web-vue/src/api/modules/xianyu.ts`
- Create: `web-vue/src/views/xianyu/components/XianyuChatAiConfigDialog.vue`

- [ ] **Step 1: Make the type checker fail on the missing frontend AI APIs**

First, in `web-vue/src/views/xianyu/components/XianyuChatPanel.vue`, add the imports you know you will need:

```ts
import {
  getXianyuChatAiConfig,
  updateXianyuChatAiConfig,
  getXianyuChatAiSessions,
  updateXianyuChatAiSession,
  testXianyuChatAi,
  type XianyuChatAiConfig,
  type XianyuChatAiSessionState,
} from '@/api/modules/xianyu'
import XianyuChatAiConfigDialog from './XianyuChatAiConfigDialog.vue'
```

Then run:

```bash
cd web-vue && ./node_modules/.bin/vue-tsc --noEmit
```

Expected: FAIL with “no exported member” / “cannot find module './XianyuChatAiConfigDialog.vue'”.

- [ ] **Step 2: Add the frontend AI types and request helpers**

Update `web-vue/src/api/modules/xianyu.ts` with:

```ts
export interface XianyuChatAiConfig {
  enabled: boolean
  base_url: string
  model: string
  system_prompt: string
  temperature: number
  api_key_configured: boolean
  api_key_masked: string
}

export interface XianyuChatAiConfigUpdatePayload {
  enabled: boolean
  base_url: string
  api_key: string
  model: string
  system_prompt: string
  temperature: number
}

export interface XianyuChatAiSessionState {
  cid: string
  enabled: boolean
}

export interface XianyuChatAiSessionUpdatePayload {
  enabled: boolean
}

export function getXianyuChatAiConfig() {
  return request.get<ApiResponse<XianyuChatAiConfig>>('/xianyu/chat/ai/config')
}

export function updateXianyuChatAiConfig(payload: XianyuChatAiConfigUpdatePayload) {
  return request.post<ApiResponse<XianyuChatAiConfig>>('/xianyu/chat/ai/config', payload)
}

export function getXianyuChatAiSessions(cids: string[]) {
  return request.get<ApiResponse<XianyuChatAiSessionState[]>>('/xianyu/chat/ai/sessions', { cid: cids })
}

export function updateXianyuChatAiSession(cid: string, payload: XianyuChatAiSessionUpdatePayload) {
  return request.post<ApiResponse<XianyuChatAiSessionState>>(`/xianyu/chat/ai/sessions/${cid}`, payload)
}

export function testXianyuChatAi(payload: { text: string; cid?: string }) {
  return request.post<ApiResponse<{ reply: string }>>('/xianyu/chat/ai/test', payload)
}
```

- [ ] **Step 3: Create the AI config dialog component**

Create `web-vue/src/views/xianyu/components/XianyuChatAiConfigDialog.vue`:

```vue
<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  saving: boolean
  testing: boolean
  modelValue: {
    enabled: boolean
    base_url: string
    api_key: string
    model: string
    system_prompt: string
    temperature: number
    api_key_masked?: string
    api_key_configured?: boolean
  }
}>()

const emit = defineEmits<{
  'update:visible': [boolean]
  save: [typeof props.modelValue]
  test: [typeof props.modelValue]
}>()

const form = reactive({ ...props.modelValue })
watch(() => props.modelValue, (value) => Object.assign(form, value), { deep: true })
const title = computed(() => 'AI 配置')
</script>

<template>
  <el-dialog :model-value="visible" :title="title" width="680px" @close="emit('update:visible', false)">
    <el-form label-width="110px">
      <el-form-item label="Base URL"><el-input v-model="form.base_url" /></el-form-item>
      <el-form-item label="API Key"><el-input v-model="form.api_key" show-password placeholder="留空则保留当前 Key" /></el-form-item>
      <el-form-item label="Model"><el-input v-model="form.model" /></el-form-item>
      <el-form-item label="Temperature"><el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" /></el-form-item>
      <el-form-item label="Prompt"><el-input v-model="form.system_prompt" type="textarea" :rows="6" /></el-form-item>
      <el-alert v-if="form.api_key_configured" :title="`已配置 Key：${form.api_key_masked || ''}`" type="success" :closable="false" />
    </el-form>
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button :loading="testing" @click="emit('test', { ...form })">测试回复</el-button>
      <el-button type="primary" :loading="saving" @click="emit('save', { ...form })">保存</el-button>
    </template>
  </el-dialog>
</template>
```

- [ ] **Step 4: Run type-check and lint**

Run:

```bash
cd web-vue && ./node_modules/.bin/vue-tsc --noEmit && ./node_modules/.bin/eslint src/api/modules/xianyu.ts src/views/xianyu/components/XianyuChatAiConfigDialog.vue
```

Expected: PASS (warnings acceptable only if they were already present before this task).

- [ ] **Step 5: Commit the frontend AI surface**

```bash
git add web-vue/src/api/modules/xianyu.ts web-vue/src/views/xianyu/components/XianyuChatAiConfigDialog.vue web-vue/src/views/xianyu/components/XianyuChatPanel.vue
git commit -m "feat: add xianyu chat ai config dialog"
```

---

### Task 7: Integrate AI controls and session markers into `XianyuChatPanel.vue`

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuChatPanel.vue`

- [ ] **Step 1: Make the panel fail type-check with the new AI state refs**

Add these references in `XianyuChatPanel.vue` before implementing them:

```ts
const chatAiConfig = ref<XianyuChatAiConfig | null>(null)
const chatAiConfigDialogVisible = ref(false)
const chatAiConfigSaving = ref(false)
const chatAiTesting = ref(false)
const sessionAiStateMap = ref<Record<string, boolean>>({})
const currentSessionAiEnabled = computed(() => Boolean(activeCid.value && sessionAiStateMap.value[activeCid.value]))
```

And add these template bindings to the current account row and session items:

```vue
<el-switch v-model="chatAiConfig.enabled" />
<el-switch :model-value="currentSessionAiEnabled" />
<XianyuChatAiConfigDialog />
<span class="chat-session__ai-state">{{ sessionAiStateMap[session.cid] ? 'AI 开' : 'AI 关' }}</span>
```

Then run:

```bash
cd web-vue && ./node_modules/.bin/vue-tsc --noEmit
```

Expected: FAIL because the methods and props are not wired yet.

- [ ] **Step 2: Implement AI config loading, saving, and testing**

In `XianyuChatPanel.vue`, add:

```ts
async function loadChatAiConfig() {
  const response = await getXianyuChatAiConfig()
  chatAiConfig.value = {
    ...response.data,
    api_key: '',
  }
}

async function saveChatAiConfig(payload: {
  enabled: boolean
  base_url: string
  api_key: string
  model: string
  system_prompt: string
  temperature: number
}) {
  chatAiConfigSaving.value = true
  try {
    const response = await updateXianyuChatAiConfig(payload)
    chatAiConfig.value = { ...response.data, api_key: '' }
    chatAiConfigDialogVisible.value = false
    ElMessage.success('AI 配置已保存')
  } finally {
    chatAiConfigSaving.value = false
  }
}

async function handleTestChatAi(payload: { text?: string } & Record<string, any>) {
  chatAiTesting.value = true
  try {
    const sampleText = activeCid.value && activeSession.value
      ? `${activeSession.value.item_title || '当前商品'}，这个还在吗？`
      : '你好，在吗？'
    const response = await testXianyuChatAi({ text: sampleText, cid: activeCid.value || undefined })
    ElMessage.success(`测试成功：${response.data.reply}`)
  } finally {
    chatAiTesting.value = false
  }
}
```

- [ ] **Step 3: Implement session-state loading and toggles**

Still in `XianyuChatPanel.vue`, add:

```ts
async function loadChatAiSessionStates() {
  const cids = sessions.value.map((item) => item.cid).filter(Boolean)
  if (!cids.length) {
    sessionAiStateMap.value = {}
    return
  }
  const response = await getXianyuChatAiSessions(cids)
  sessionAiStateMap.value = Object.fromEntries(response.data.map((item) => [item.cid, item.enabled]))
}

async function handleToggleGlobalAi(enabled: boolean) {
  if (!chatAiConfig.value) return
  await saveChatAiConfig({
    enabled,
    base_url: chatAiConfig.value.base_url,
    api_key: '',
    model: chatAiConfig.value.model,
    system_prompt: chatAiConfig.value.system_prompt,
    temperature: chatAiConfig.value.temperature,
  })
}

async function handleToggleCurrentSessionAi(enabled: boolean) {
  if (!activeCid.value) return
  await updateXianyuChatAiSession(activeCid.value, { enabled })
  sessionAiStateMap.value = { ...sessionAiStateMap.value, [activeCid.value]: enabled }
  ElMessage.success(enabled ? '当前会话已启用 AI' : '当前会话已关闭 AI')
}
```

Call `loadChatAiConfig()` and `loadChatAiSessionStates()` from `onMounted()` and again after `loadConversations()` refreshes the session list.

- [ ] **Step 4: Move the controls into the left-top account row and add the session badge**

Update the template in `XianyuChatPanel.vue` so the current account row becomes:

```vue
<div class="chat-account">
  <img v-if="currentAccount.avatar" :src="currentAccount.avatar" :alt="currentAccount.display_name" class="chat-account__avatar">
  <div v-else class="chat-account__avatar chat-account__avatar--placeholder">{{ currentAccount.display_name.slice(0, 1) || '鱼' }}</div>

  <div class="chat-account__main">
    <strong>{{ currentAccount.display_name }}</strong>
    <span>{{ currentAccount.user_id || '账号识别中...' }}</span>
  </div>

  <div class="chat-account__ai-actions" v-if="chatAiConfig">
    <el-switch
      :model-value="chatAiConfig.enabled"
      inline-prompt
      active-text="AI 总开"
      inactive-text="AI 总关"
      @change="handleToggleGlobalAi"
    />
    <el-switch
      :model-value="currentSessionAiEnabled"
      :disabled="!activeCid"
      inline-prompt
      active-text="当前会话 AI"
      inactive-text="当前会话 AI"
      @change="handleToggleCurrentSessionAi"
    />
    <el-button size="small" @click="chatAiConfigDialogVisible = true">AI 配置</el-button>
  </div>
</div>
```

And in each session item title row add:

```vue
<span class="chat-session__ai-state" :class="sessionAiStateMap[session.cid] ? 'is-enabled' : 'is-disabled'">
  {{ sessionAiStateMap[session.cid] ? 'AI 开' : 'AI 关' }}
</span>
```

Also render the dialog at the bottom of the template:

```vue
<XianyuChatAiConfigDialog
  v-if="chatAiConfig"
  :visible="chatAiConfigDialogVisible"
  :saving="chatAiConfigSaving"
  :testing="chatAiTesting"
  :model-value="chatAiConfig"
  @update:visible="chatAiConfigDialogVisible = $event"
  @save="saveChatAiConfig"
  @test="handleTestChatAi"
/>
```

- [ ] **Step 5: Add the scoped styles for the new controls**

Add styles in `XianyuChatPanel.vue`:

```scss
.chat-account {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
}

.chat-account__ai-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.chat-session__ai-state {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  line-height: 1.4;
}

.chat-session__ai-state.is-enabled {
  background: rgba(34, 197, 94, 0.18);
  color: #8ff0b3;
}

.chat-session__ai-state.is-disabled {
  background: rgba(148, 163, 184, 0.16);
  color: #b9c4d4;
}
```

- [ ] **Step 6: Run type-check and lint again**

Run:

```bash
cd web-vue && ./node_modules/.bin/vue-tsc --noEmit && ./node_modules/.bin/eslint src/views/xianyu/components/XianyuChatPanel.vue src/views/xianyu/components/XianyuChatAiConfigDialog.vue src/api/modules/xianyu.ts
```

Expected: PASS.

- [ ] **Step 7: Manually verify in the browser**

With the existing dev servers running (`web-vue` on `http://localhost:3000`, backend on `http://localhost:5000`):

1. 打开 `http://localhost:3000/xianyu`
2. 进入聊天 tab
3. 确认左侧顶部账号行出现：`AI 总开关`、`当前会话 AI`、`AI 配置`
4. 切换不同会话，确认“当前会话 AI”状态会跟着变
5. 确认左侧每个会话项显示 `AI 开 / AI 关`
6. 打开 AI 配置弹窗，保存一套配置，刷新后仍能读回
7. 打开某个会话 AI，再从闲鱼对端发送一条文本消息，确认页面在线时会自动回复一次

- [ ] **Step 8: Commit the chat panel integration**

```bash
git add web-vue/src/views/xianyu/components/XianyuChatPanel.vue web-vue/src/views/xianyu/components/XianyuChatAiConfigDialog.vue web-vue/src/api/modules/xianyu.ts
git commit -m "feat: add xianyu chat ai controls"
```

---

### Task 8: Run the full verification suite

**Files:**
- Modify if needed: any files touched by fixes from verification

- [ ] **Step 1: Run the backend AI test suite**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest   tests/test_xianyu_chat_ai_store.py   tests/test_xianyu_chat_ai_api.py   tests/test_xianyu_chat_ai_trigger.py   tests/test_xianyu_chat_ai_routes.py   tests/test_xianyu_chat_ai_ws.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend type-check and lint**

Run:

```bash
cd web-vue && ./node_modules/.bin/vue-tsc --noEmit && ./node_modules/.bin/eslint src/api/modules/xianyu.ts src/views/xianyu/components/XianyuChatAiConfigDialog.vue src/views/xianyu/components/XianyuChatPanel.vue
```

Expected: PASS.

- [ ] **Step 3: Run a production build for regression coverage**

Run:

```bash
cd web-vue && npm run build
```

Expected: PASS with a generated `dist/` bundle.

- [ ] **Step 4: Commit any final verification fixes**

```bash
git add backend web-vue
git commit -m "chore: finalize xianyu chat ai takeover"
```
