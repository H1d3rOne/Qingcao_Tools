# 闲鱼浏览器辅助扫码登录 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Playwright 驱动真实浏览器会话完成闲鱼扫码登录，替代当前默认的纯 API 扫码链路，解决“刚扫码就过期”问题并继续把 Cookie 保存到统一本地文件。

**Architecture:** 后端新增 `browser_login.py` 封装浏览器扫码会话管理器，由 `XianyuService` 负责启动、轮询、取消会话以及保存 Cookie；FastAPI 暴露 `start/status/cancel` 三个接口；前端登录页默认切换到浏览器扫码接口，并在成功后继续复用现有登录态初始化逻辑。

**Tech Stack:** FastAPI、Pydantic、Playwright（Python）、Requests/Cookie Store、Vue 3、Element Plus、Pytest

---

### Task 1: 为浏览器扫码会话管理器写失败测试并补依赖声明

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/tests/test_xianyu_browser_login_manager.py`
- Test: `backend/tests/test_xianyu_browser_login_manager.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from xianyu_client.cookie_store import load_xianyu_cookie_string

from app.modules.xianyu.browser_login import XianyuBrowserLoginManager


def test_browser_login_manager_keeps_single_active_session(tmp_path: Path):
    manager = XianyuBrowserLoginManager(config_dir=tmp_path)

    first = manager.create_session(
        qrcode_image='data:image/png;base64,first',
        poller=None,
        cleanup=None,
        expires_in=300,
    )
    second = manager.create_session(
        qrcode_image='data:image/png;base64,second',
        poller=None,
        cleanup=None,
        expires_in=300,
    )

    assert first.session_id != second.session_id
    assert manager.get_session(first.session_id) is None
    assert manager.get_session(second.session_id).qrcode_image == 'data:image/png;base64,second'


def test_browser_login_manager_persists_cookie_on_success(tmp_path: Path):
    manager = XianyuBrowserLoginManager(config_dir=tmp_path)
    session = manager.create_session(
        qrcode_image='data:image/png;base64,qr',
        poller=None,
        cleanup=None,
        expires_in=300,
    )

    result = manager.mark_success(
        session.session_id,
        cookie_string='cna=test; cookie2=abc; unb=user',
    )

    assert result['is_logged_in'] is True
    assert result['status'] == 'success'
    assert load_xianyu_cookie_string(config_dir=tmp_path) == 'cna=test; cookie2=abc; unb=user'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_browser_login_manager.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.xianyu.browser_login'`

- [ ] **Step 3: Add dependency declaration before implementation**

```txt
# browser automation
playwright>=1.52.0,<1.53
```

Add the line near other runtime dependencies in `backend/requirements.txt`.

- [ ] **Step 4: Re-run the failing test**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_browser_login_manager.py -q`
Expected: still FAIL, but now only because manager implementation is missing

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/tests/test_xianyu_browser_login_manager.py
git commit -m "test: add xianyu browser login manager specs"
```

### Task 2: 实现浏览器扫码会话管理器与 Cookie 持久化

**Files:**
- Create: `backend/app/modules/xianyu/browser_login.py`
- Modify: `backend/app/modules/xianyu/__init__.py`
- Test: `backend/tests/test_xianyu_browser_login_manager.py`

- [ ] **Step 1: Write the minimal manager implementation to satisfy the first test**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time
import uuid
from typing import Any, Callable

from xianyu_client.cookie_store import save_xianyu_cookie_string


@dataclass
class XianyuBrowserLoginSession:
    session_id: str
    qrcode_image: str
    status: str = 'waiting'
    message: str = '二维码已生成，请使用闲鱼 APP 扫码'
    expires_at: int = 0
    created_at: int = field(default_factory=lambda: int(time.time()))
    login_token: str = ''
    poller: Callable[[], Any] | None = None
    cleanup: Callable[[], Any] | None = None


class XianyuBrowserLoginManager:
    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self._active_session_id: str | None = None
        self._sessions: dict[str, XianyuBrowserLoginSession] = {}

    def create_session(self, *, qrcode_image: str, poller=None, cleanup=None, expires_in: int = 300) -> XianyuBrowserLoginSession:
        if self._active_session_id:
            self._sessions.pop(self._active_session_id, None)
        session = XianyuBrowserLoginSession(
            session_id=uuid.uuid4().hex[:12],
            qrcode_image=qrcode_image,
            expires_at=int(time.time()) + int(expires_in),
            poller=poller,
            cleanup=cleanup,
        )
        self._sessions[session.session_id] = session
        self._active_session_id = session.session_id
        return session

    def get_session(self, session_id: str) -> XianyuBrowserLoginSession | None:
        session = self._sessions.get(session_id)
        if session and session.expires_at <= int(time.time()) and session.status not in {'success', 'cancelled'}:
            session.status = 'expired'
            session.message = '二维码已过期，请重新获取'
        return session

    def mark_success(self, session_id: str, *, cookie_string: str) -> dict[str, Any]:
        session = self._require_session(session_id)
        save_xianyu_cookie_string(cookie_string, config_dir=self.config_dir, source='browser_qrcode')
        session.status = 'success'
        session.message = '登录成功'
        session.login_token = cookie_string
        return {
            'success': True,
            'message': session.message,
            'status': session.status,
            'is_logged_in': True,
            'login_token': cookie_string,
        }

    def _require_session(self, session_id: str) -> XianyuBrowserLoginSession:
        session = self.get_session(session_id)
        if not session:
            raise ValueError('扫码会话不存在或已失效')
        return session
```

- [ ] **Step 2: Run the manager tests and verify they pass**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_browser_login_manager.py -q`
Expected: PASS

- [ ] **Step 3: Export the new manager types from module init**

```python
from app.modules.xianyu.browser_login import (
    XianyuBrowserLoginManager,
    XianyuBrowserLoginSession,
)
```

And add both names to `__all__` in `backend/app/modules/xianyu/__init__.py`.

- [ ] **Step 4: Re-run the manager tests after export change**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_browser_login_manager.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/xianyu/browser_login.py backend/app/modules/xianyu/__init__.py
git commit -m "feat: add xianyu browser login manager"
```

### Task 3: 为浏览器扫码 API 写失败测试并补后端 schema

**Files:**
- Modify: `backend/app/modules/xianyu/schemas.py`
- Create: `backend/tests/test_xianyu_browser_login_api.py`
- Test: `backend/tests/test_xianyu_browser_login_api.py`

- [ ] **Step 1: Write the failing API test**

```python
from fastapi.testclient import TestClient

from app.api.deps import get_xianyu_service
from app.main import app


class FakeXianyuBrowserLoginService:
    def start_browser_login(self):
        return {
            'success': True,
            'message': '二维码已生成，请使用闲鱼 APP 扫码',
            'session_id': 'session-1',
            'qrcode_image': 'data:image/png;base64,qr',
            'expires_in': 300,
        }

    def get_browser_login_status(self, session_id: str):
        assert session_id == 'session-1'
        return {
            'success': True,
            'message': '登录成功',
            'status': 'success',
            'is_logged_in': True,
            'login_token': 'cna=test; cookie2=abc',
        }

    def cancel_browser_login(self, session_id: str):
        assert session_id == 'session-1'
        return {'success': True, 'message': '已取消扫码登录'}


def test_xianyu_browser_login_endpoints_roundtrip():
    app.dependency_overrides[get_xianyu_service] = lambda: FakeXianyuBrowserLoginService()
    client = TestClient(app)

    start_resp = client.post('/api/v1/xianyu/auth/browser-qrcode/start')
    assert start_resp.status_code == 200
    assert start_resp.json()['session_id'] == 'session-1'

    status_resp = client.get('/api/v1/xianyu/auth/browser-qrcode/status', params={'session_id': 'session-1'})
    assert status_resp.status_code == 200
    assert status_resp.json()['status'] == 'success'
    assert status_resp.json()['is_logged_in'] is True

    cancel_resp = client.post('/api/v1/xianyu/auth/browser-qrcode/cancel', json={'session_id': 'session-1'})
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()['success'] is True

    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_browser_login_api.py -q`
Expected: FAIL with missing schema or missing route errors

- [ ] **Step 3: Add browser login schema models**

```python
class XianyuBrowserLoginStartResponse(BaseModel):
    success: bool = Field(True)
    message: str = Field('')
    session_id: str = Field('')
    qrcode_image: Optional[str] = Field(None)
    expires_in: int = Field(0)


class XianyuBrowserLoginStatusResponse(BaseModel):
    success: bool = Field(True)
    message: str = Field('')
    status: str = Field('waiting')
    is_logged_in: bool = Field(False)
    login_token: Optional[str] = Field(None)


class XianyuBrowserLoginCancelRequest(BaseModel):
    session_id: str = Field(..., min_length=1)


class XianyuBrowserLoginCancelResponse(BaseModel):
    success: bool = Field(True)
    message: str = Field('')
```

- [ ] **Step 4: Re-run the API test and confirm it still fails on route implementation**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_browser_login_api.py -q`
Expected: FAIL only because route/service implementation is missing

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/xianyu/schemas.py backend/tests/test_xianyu_browser_login_api.py
git commit -m "test: add xianyu browser login api specs"
```

### Task 4: 实现后端浏览器扫码 service 与路由

**Files:**
- Modify: `backend/app/modules/xianyu/service.py`
- Modify: `backend/app/api/v1/xianyu.py`
- Modify: `backend/app/modules/xianyu/__init__.py`
- Test: `backend/tests/test_xianyu_browser_login_api.py`
- Test: `backend/tests/test_xianyu_browser_login_manager.py`

- [ ] **Step 1: Add browser login manager initialization to `XianyuService.__init__`**

```python
from app.modules.xianyu.browser_login import XianyuBrowserLoginManager

self._browser_profile_dir = Path.cwd() / 'config' / 'xianyu_browser_profile'
self._browser_login_manager = XianyuBrowserLoginManager(config_dir=self._xianyu_cookie_path.parent)
```

- [ ] **Step 2: Implement service methods with a Playwright fallback guard**

```python
def start_browser_login(self) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return {'success': False, 'message': f'浏览器扫码依赖不可用: {exc}', 'session_id': '', 'qrcode_image': None, 'expires_in': 0}

    # 第一版只保证接口、状态机和持久化链路可用；真实页面接线在下个步骤补齐
    session = self._browser_login_manager.create_session(
        qrcode_image='',
        expires_in=300,
    )
    return {
        'success': True,
        'message': '二维码初始化中，请稍候',
        'session_id': session.session_id,
        'qrcode_image': session.qrcode_image,
        'expires_in': 300,
    }


def get_browser_login_status(self, session_id: str) -> dict[str, Any]:
    session = self._browser_login_manager.get_session(session_id)
    if not session:
        return {'success': False, 'message': '扫码会话不存在或已失效', 'status': 'failed', 'is_logged_in': False}
    return {
        'success': True,
        'message': session.message,
        'status': session.status,
        'is_logged_in': session.status == 'success',
        'login_token': session.login_token or None,
    }


def cancel_browser_login(self, session_id: str) -> dict[str, Any]:
    session = self._browser_login_manager.get_session(session_id)
    if not session:
        return {'success': False, 'message': '扫码会话不存在或已失效'}
    session.status = 'cancelled'
    session.message = '已取消扫码登录'
    if session.cleanup:
        session.cleanup()
    return {'success': True, 'message': session.message}
```

- [ ] **Step 3: Expose the new routes**

```python
@router.post('/auth/browser-qrcode/start', response_model=XianyuBrowserLoginStartResponse)
async def start_xianyu_browser_qrcode(service: XianyuService = Depends(get_xianyu_service)):
    return XianyuBrowserLoginStartResponse(**service.start_browser_login())


@router.get('/auth/browser-qrcode/status', response_model=XianyuBrowserLoginStatusResponse)
async def get_xianyu_browser_qrcode_status(session_id: str, service: XianyuService = Depends(get_xianyu_service)):
    return XianyuBrowserLoginStatusResponse(**service.get_browser_login_status(session_id))


@router.post('/auth/browser-qrcode/cancel', response_model=XianyuBrowserLoginCancelResponse)
async def cancel_xianyu_browser_qrcode(request: XianyuBrowserLoginCancelRequest, service: XianyuService = Depends(get_xianyu_service)):
    return XianyuBrowserLoginCancelResponse(**service.cancel_browser_login(request.session_id))
```

- [ ] **Step 4: Add the real Playwright page bootstrap path**

```python
def start_browser_login(self) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(self._browser_profile_dir),
            headless=True,
        )
        page = context.new_page()
        page.goto('https://passport.goofish.com/mini_login.htm?lang=zh_cn&appName=xianyu&appEntrance=web', wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(2000)

        qrcode_image = ''
        with contextlib.suppress(Exception):
            qrcode_image = page.locator('img').first.get_attribute('src') or ''

        session = self._browser_login_manager.create_session(
            qrcode_image=qrcode_image,
            cleanup=lambda: (context.close(), playwright.stop()),
            expires_in=300,
        )
        return {
            'success': True,
            'message': '二维码已生成，请使用闲鱼 APP 扫码',
            'session_id': session.session_id,
            'qrcode_image': qrcode_image,
            'expires_in': 300,
        }
    except Exception as exc:
        return {'success': False, 'message': f'启动浏览器扫码失败: {exc}', 'session_id': '', 'qrcode_image': None, 'expires_in': 0}
```

If no `img/src` is available, replace this step during implementation with a QR area screenshot converted to `data:image/png;base64,...`.

- [ ] **Step 5: Run backend tests**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_browser_login_manager.py tests/test_xianyu_browser_login_api.py tests/test_xianyu_auth_api.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/xianyu/service.py backend/app/api/v1/xianyu.py backend/app/modules/xianyu/__init__.py
git commit -m "feat: add xianyu browser qrcode backend api"
```

### Task 5: 为前端登录页写接口映射并切换到浏览器扫码链路

**Files:**
- Modify: `web-vue/src/api/modules/xianyu.ts`
- Modify: `web-vue/src/views/xianyu/login/index.vue`

- [ ] **Step 1: Add front-end API types and request functions**

```ts
export interface XianyuBrowserLoginStartResponse {
  success: boolean
  message: string
  session_id: string
  qrcode_image?: string | null
  expires_in: number
}

export interface XianyuBrowserLoginStatusResponse {
  success: boolean
  message: string
  status: 'waiting' | 'scanned' | 'confirmed' | 'success' | 'expired' | 'failed' | 'cancelled' | string
  is_logged_in: boolean
  login_token?: string | null
}

export function startXianyuBrowserLogin() {
  return request.post<XianyuBrowserLoginStartResponse>('/xianyu/auth/browser-qrcode/start')
}

export function getXianyuBrowserLoginStatus(sessionId: string) {
  return request.get<XianyuBrowserLoginStatusResponse>('/xianyu/auth/browser-qrcode/status', { session_id: sessionId })
}

export function cancelXianyuBrowserLogin(sessionId: string) {
  return request.post<{ success: boolean; message: string }>('/xianyu/auth/browser-qrcode/cancel', { session_id: sessionId })
}
```

- [ ] **Step 2: Replace login page state from `qrcodeToken` to `browserLoginSessionId`**

```ts
const browserLoginSessionId = ref('')
```

And remove the default path that starts polling with `checkXianyuLogin({ qrcode_token: token })`.

- [ ] **Step 3: Replace QR generation flow**

```ts
const generateQrcode = async () => {
  loading.value = true
  error.value = ''
  qrcodeImage.value = ''
  stopPolling()

  try {
    const response = await startXianyuBrowserLogin()
    if (!response.success || !response.session_id || !response.qrcode_image) {
      throw new Error(response.message || '获取二维码失败')
    }

    browserLoginSessionId.value = response.session_id
    qrcodeImage.value = response.qrcode_image
    loading.value = false
    ElMessage.success(response.message || '二维码已生成，请使用闲鱼 APP 扫码')
    startPolling(response.session_id)
  } catch (err: unknown) {
    loading.value = false
    error.value = err instanceof Error ? err.message : '获取二维码失败'
    ElMessage.error(error.value)
  }
}
```

- [ ] **Step 4: Replace status polling flow and map browser states**

```ts
const startPolling = (sessionId: string) => {
  checkingLogin.value = true
  checkingText.value = '等待扫码中...'

  pollTimer = window.setInterval(async () => {
    try {
      const result = await getXianyuBrowserLoginStatus(sessionId)
      checkingText.value = result.message || '等待扫码中...'
      if (result.status === 'expired' || result.status === 'failed' || result.status === 'cancelled') {
        stopPolling()
        error.value = result.message || '二维码已失效，请重新获取'
        ElMessage.error(error.value)
        return
      }
      if (result.is_logged_in) {
        stopPolling()
        await userStore.checkAuthStatus()
        userStore.loginSuccess((await getXianyuAuthStatus()).user_info as Record<string, unknown> | null)
        ElMessage.success('登录成功！')
        router.push(getRedirectTarget())
      }
    } catch (err: unknown) {
      stopPolling()
      error.value = err instanceof Error ? err.message : '登录状态检查失败'
      ElMessage.error(error.value)
    }
  }, 2000)
}
```

- [ ] **Step 5: Cancel browser session when refreshing or unmounting**

```ts
const stopPolling = async () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (expireTimer) {
    clearTimeout(expireTimer)
    expireTimer = null
  }
  if (browserLoginSessionId.value) {
    try {
      await cancelXianyuBrowserLogin(browserLoginSessionId.value)
    } catch {
      // ignore cancellation errors
    }
    browserLoginSessionId.value = ''
  }
  checkingLogin.value = false
}
```

If this causes refresh-triggered cancellation too early, split it into `clearTimers()` and `cancelActiveBrowserSession()` during implementation; keep the final code behaviorally equivalent.

- [ ] **Step 6: Run front-end verification**

Run: `cd web-vue && npm run build`
Expected: `vue-tsc && vite build` succeeds

- [ ] **Step 7: Commit**

```bash
git add web-vue/src/api/modules/xianyu.ts web-vue/src/views/xianyu/login/index.vue
git commit -m "feat: use browser qrcode flow in xianyu login page"
```

### Task 6: 端到端安装与手工验证

**Files:**
- Modify: `backend/requirements.txt`
- Optional runtime path: `backend/config/xianyu_browser_profile/`
- Optional runtime file: `backend/config/xianyu_cookies.json`

- [ ] **Step 1: Install browser automation dependency**

Run: `cd backend && ./.venv/bin/python -m pip install -r requirements.txt`
Expected: installs `playwright`

- [ ] **Step 2: Install Chromium runtime**

Run: `cd backend && ./.venv/bin/python -m playwright install chromium`
Expected: browser download/install completes successfully

- [ ] **Step 3: Run focused backend tests**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_browser_login_manager.py tests/test_xianyu_browser_login_api.py tests/test_xianyu_auth_api.py -q`
Expected: PASS

- [ ] **Step 4: Run front-end build**

Run: `cd web-vue && npm run build`
Expected: PASS

- [ ] **Step 5: Manual verification**

Run:
```bash
cd backend && ./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 5000
```

Then verify in the browser:
1. Open `http://localhost:3000/xianyu/login`
2. Confirm QR is displayed
3. Scan with 闲鱼 APP
4. Confirm login on the phone
5. Verify page jumps to `/xianyu`
6. Verify `backend/config/xianyu_cookies.json` now contains the saved cookie string
7. Verify `GET /api/v1/xianyu/auth/status` returns `is_logged_in: true`

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt
# runtime-generated profile/cookie files should not be committed
git commit -m "chore: verify xianyu browser qrcode login flow"
```

---

## Self-Review

### Spec coverage
- 浏览器扫码会话管理器：Task 1-2
- `start/status/cancel` 接口：Task 3-4
- 前端默认切换新扫码接口：Task 5
- 统一 Cookie 持久化：Task 2、Task 4、Task 6
- 依赖安装与手工验证：Task 6
- 保留 Cookie 登录兜底：Task 5 只替换二维码链路，不改 Cookie 登录 tab

### Placeholder scan
- 未使用 `TODO/TBD`
- 每个实现步骤都给出了目标代码块、命令和期望结果
- 风险点（如二维码非 `img/src`）已在对应步骤中标明具体替换策略

### Type consistency
- 后端方法统一使用：`start_browser_login / get_browser_login_status / cancel_browser_login`
- 前端接口统一对应：`startXianyuBrowserLogin / getXianyuBrowserLoginStatus / cancelXianyuBrowserLogin`
- 状态字段统一为：`waiting | scanned | confirmed | success | expired | failed | cancelled`
