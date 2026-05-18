# 闲鱼项目内拉起聊天会话 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让详情弹窗的“联系卖家”在项目内直接打开闲鱼聊天会话，失败时只提示失败不跳原站。

**Architecture:** 后端新增 `open-session` 接口，先匹配已有会话，再尝试最小化创建/拉起会话；前端详情页调用新接口并把 `cid` 传给聊天面板，聊天面板根据外部指定 `cid` 自动切换会话。

**Tech Stack:** FastAPI、Pydantic、httpx/websockets、Vue 3、Element Plus、ESLint、Pytest

---

### Task 1: 为后端“打开会话”能力写失败测试并补 schema

**Files:**
- Modify: `backend/app/modules/xianyu/schemas.py`
- Create: `backend/tests/test_xianyu_chat_open_session.py`
- Test: `backend/tests/test_xianyu_chat_open_session.py`

- [ ] **Step 1: Write the failing test**

```python
from app.modules.xianyu.service import XianyuService
from app.modules.xianyu.schemas import XianyuChatConversation
import asyncio


def test_open_chat_session_prefers_existing_conversation(monkeypatch):
    service = XianyuService()

    existing = XianyuChatConversation(
        cid='cid-1',
        session_id='cid-1',
        session_type=1,
        biz_type='1',
        title='卖家会话',
        peer_user_id='2218736549452',
        peer_display_name='卖家',
        peer_avatar='',
        item_id='101',
        item_title='测试商品',
        item_image='',
        last_message_id='',
        last_message_summary='',
        last_message_time=0,
        last_message_time_text='',
        unread_count=0,
        red_point=0,
        top_rank=0,
        muted=False,
        visible=True,
        can_send=True,
    )

    async def fake_list_chat_conversations(offset=0, limit=20):
        from app.modules.xianyu.schemas import XianyuChatConversationPage
        return XianyuChatConversationPage(total=1, offset=0, limit=40, conversations=[existing])

    monkeypatch.setattr(service, 'list_chat_conversations', fake_list_chat_conversations)

    result = asyncio.run(service.open_chat_session(item_id='101', peer_user_id='2218736549452'))

    assert result['success'] is True
    assert result['cid'] == 'cid-1'
    assert result['session'].peer_user_id == '2218736549452'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_xianyu_chat_open_session.py -q`
Expected: FAIL with `AttributeError` or missing `open_chat_session`

- [ ] **Step 3: Add request/response schema placeholders**

```python
class XianyuChatOpenSessionRequest(BaseModel):
    item_id: str = Field(..., min_length=1)
    peer_user_id: str = Field(..., min_length=1)

class XianyuChatOpenSessionResponse(BaseModel):
    success: bool = True
    message: str = ''
    cid: str = ''
    session: XianyuChatConversation | None = None
```

- [ ] **Step 4: Re-run test and confirm it still fails on service implementation**

Run: `./.venv/bin/python -m pytest tests/test_xianyu_chat_open_session.py -q`
Expected: FAIL only because service implementation is still missing

### Task 2: 实现后端 open-session 服务与路由

**Files:**
- Modify: `backend/app/modules/xianyu/service.py`
- Modify: `backend/app/modules/xianyu/__init__.py`
- Modify: `backend/app/api/v1/xianyu.py`
- Test: `backend/tests/test_xianyu_chat_open_session.py`

- [ ] **Step 1: Implement existing-session match path**

```python
async def open_chat_session(self, item_id: str, peer_user_id: str) -> dict[str, Any]:
    item_id = str(item_id or '').strip()
    peer_user_id = str(peer_user_id or '').strip()
    if not item_id or not peer_user_id:
        return {'success': False, 'message': '商品或卖家信息不完整'}

    page = await self.list_chat_conversations(offset=0, limit=40)
    exact = next((s for s in page.conversations if s.peer_user_id == peer_user_id and s.item_id == item_id), None)
    fallback = next((s for s in page.conversations if s.peer_user_id == peer_user_id), None)
    target = exact or fallback
    if target:
        return {'success': True, 'message': '已打开会话', 'cid': target.cid, 'session': target}

    return await self._open_chat_session_via_bootstrap(item_id=item_id, peer_user_id=peer_user_id)
```

- [ ] **Step 2: Add failing test for creation path**

```python
def test_open_chat_session_returns_failure_when_creation_unavailable(monkeypatch):
    service = XianyuService()

    async def fake_list_chat_conversations(offset=0, limit=20):
        from app.modules.xianyu.schemas import XianyuChatConversationPage
        return XianyuChatConversationPage(total=0, offset=0, limit=40, conversations=[])

    async def fake_open_chat_session_via_bootstrap(item_id: str, peer_user_id: str):
        return {'success': False, 'message': '创建会话失败'}

    monkeypatch.setattr(service, 'list_chat_conversations', fake_list_chat_conversations)
    monkeypatch.setattr(service, '_open_chat_session_via_bootstrap', fake_open_chat_session_via_bootstrap)

    import asyncio
    result = asyncio.run(service.open_chat_session(item_id='101', peer_user_id='222'))

    assert result == {'success': False, 'message': '创建会话失败'}
```

- [ ] **Step 3: Implement bootstrap create path (minimal, non-send)**

```python
async def _open_chat_session_via_bootstrap(self, item_id: str, peer_user_id: str) -> dict[str, Any]:
    chat_client = await self.open_chat_ws_client()
    try:
        response = await chat_client.send_rpc('/r/Conversation/listNewest', [0, 40])
        self._ensure_chat_rpc_success(response, '获取闲鱼聊天会话失败')
        conversations = [
            self._map_chat_conversation(item, chat_client.profile)
            for item in response.get('body') or []
            if isinstance(item, dict)
        ]
        exact = next((s for s in conversations if s.peer_user_id == peer_user_id and s.item_id == item_id), None)
        fallback = next((s for s in conversations if s.peer_user_id == peer_user_id), None)
        target = exact or fallback
        if target:
            return {'success': True, 'message': '已打开会话', 'cid': target.cid, 'session': target}
        return {'success': False, 'message': '项目内暂未能直接创建该卖家的会话，请先在闲鱼建立一次聊天'}
    finally:
        await chat_client.close()
```

- [ ] **Step 4: Expose route**

```python
@router.post('/chat/open-session', response_model=XianyuChatOpenSessionResponse)
async def open_xianyu_chat_session(request: XianyuChatOpenSessionRequest, service: XianyuService = Depends(get_xianyu_service)):
    result = await service.open_chat_session(item_id=request.item_id, peer_user_id=request.peer_user_id)
    return XianyuChatOpenSessionResponse(**result)
```

- [ ] **Step 5: Run backend tests**

Run: `./.venv/bin/python -m pytest tests/test_xianyu_chat_open_session.py tests/test_xianyu_auth_api.py -q`
Expected: PASS

### Task 3: 前端详情页接入 open-session 接口

**Files:**
- Modify: `web-vue/src/api/modules/xianyu.ts`
- Modify: `web-vue/src/views/xianyu/index.vue`

- [ ] **Step 1: Add API types and request function**

```ts
export interface XianyuChatOpenSessionPayload {
  item_id: string
  peer_user_id: string
}

export interface XianyuChatOpenSessionResponse {
  success: boolean
  message: string
  cid?: string
  session?: XianyuChatConversation | null
}

export function openXianyuChatSession(payload: XianyuChatOpenSessionPayload) {
  return request.post<XianyuChatOpenSessionResponse>('/xianyu/chat/open-session', payload)
}
```

- [ ] **Step 2: Add local preferred chat state in detail page**

```ts
const preferredChatCid = ref('')
const openingChatSession = ref(false)
```

- [ ] **Step 3: Replace detail contact action**

```ts
async function contactSeller() {
  if (!detailData.value?.item_id || !detailData.value?.seller_user_id) {
    ElMessage.error('商品或卖家信息不完整，无法打开聊天')
    return
  }

  openingChatSession.value = true
  try {
    const response = await openXianyuChatSession({
      item_id: detailData.value.item_id,
      peer_user_id: detailData.value.seller_user_id,
    })
    if (!response.success || !response.cid) {
      throw new Error(response.message || '打开会话失败')
    }
    preferredChatCid.value = response.cid
    detailVisible.value = false
    activeBottomTab.value = 'chat'
    ElMessage.success(response.message || '已打开会话')
  } catch (err: any) {
    ElMessage.error(err?.message || '打开会话失败')
  } finally {
    openingChatSession.value = false
  }
}
```

- [ ] **Step 4: Bind loading and pass preferred chat cid**

```vue
<el-button type="primary" size="large" :loading="openingChatSession" @click="contactSeller">
  <el-icon><ChatDotRound /></el-icon>
  联系卖家
</el-button>

<XianyuChatPanel v-else-if="activeBottomTab === 'chat'" :current-user="xianyuUser" :preferred-cid="preferredChatCid" />
```

- [ ] **Step 5: Run ESLint**

Run: `./node_modules/.bin/eslint src/api/modules/xianyu.ts src/views/xianyu/index.vue`
Expected: 0 errors

### Task 4: 聊天面板支持外部指定会话

**Files:**
- Modify: `web-vue/src/views/xianyu/components/XianyuChatPanel.vue`

- [ ] **Step 1: Add prop**

```ts
const props = defineProps<{
  currentUser?: XianyuUserProfile | null
  preferredCid?: string
}>()
```

- [ ] **Step 2: Add helper to focus a cid**

```ts
async function focusPreferredConversation(cid: string) {
  if (!cid) return
  const session = sessions.value.find((item) => item.cid === cid)
  if (!session) {
    await loadConversations(false)
  }
  const matched = sessions.value.find((item) => item.cid === cid)
  if (!matched) return
  if (activeCid.value === matched.cid) return
  await handleSelectSession(matched)
}
```

- [ ] **Step 3: Watch prop and focus session**

```ts
watch(
  () => props.preferredCid,
  async (cid) => {
    if (!cid) return
    await focusPreferredConversation(cid)
  },
  { immediate: true }
)
```

- [ ] **Step 4: Run targeted frontend lint**

Run: `./node_modules/.bin/eslint src/views/xianyu/components/XianyuChatPanel.vue`
Expected: 0 errors

### Task 5: Full verification

**Files:**
- Verify only

- [ ] **Step 1: Run backend regression**

Run: `cd backend && ./.venv/bin/python -m pytest tests/test_xianyu_cookie_storage.py tests/test_xianyu_auth_api.py tests/test_xianyu_item_detail_mapping.py tests/test_xianyu_detail_theme_styles.py tests/test_xianyu_chat_open_session.py -q`
Expected: all pass

- [ ] **Step 2: Run frontend targeted lint**

Run: `cd web-vue && ./.node_modules/.bin/eslint src/api/modules/xianyu.ts src/views/xianyu/index.vue src/views/xianyu/components/XianyuChatPanel.vue`
Expected: 0 errors (existing warnings may remain if unrelated)

- [ ] **Step 3: Manual verification checklist**

```text
1. 搜索商品并打开详情
2. 点击“联系卖家”
3. 若已有会话：自动切到聊天并打开目标会话
4. 若无会话：提示“项目内暂未能直接创建该卖家的会话，请先在闲鱼建立一次聊天”
5. 整个过程中不跳原站、不自动发消息
```
