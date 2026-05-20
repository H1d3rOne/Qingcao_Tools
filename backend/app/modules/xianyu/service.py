"""
闲鱼搜索服务
"""
from __future__ import annotations

import asyncio
from collections import deque
import base64
import contextlib
import hashlib
import io
import inspect
import json
import random
import re
import time
import uuid
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import qrcode
import qrcode.image.svg
import websockets

from app.core.config import settings as app_settings
from app.core.config_bootstrap import get_runtime_config_dir, write_json_atomic
from app.modules.xianyu.ai_store import XianyuChatAiStore
from app.modules.xianyu.browser_login import XianyuBrowserLoginManager
from app.modules.xianyu.crypto import decrypt as xianyu_decrypt
from app.modules.xianyu.delivery_runtime import XianyuDeliveryRuntime
from app.modules.xianyu.delivery_store import XianyuDeliveryStore
from app.modules.xianyu.item_store import XianyuItemStore
from app.modules.xianyu.monitor_store import XianyuMonitorStore
from app.modules.xianyu.schemas import (
    XianyuChatAiConfig,
    XianyuChatAiConfigUpdateRequest,
    XianyuChatAiProvider,
    XianyuChatAiProviderCreateRequest,
    XianyuChatAiProviderUpdateRequest,
    XianyuChatClearResult,
    XianyuChatConversation,
    XianyuChatConversationPage,
    XianyuChatMessage,
    XianyuChatMessagePage,
    XianyuChatHealthStatus,
    XianyuChatProfile,
    XianyuChatSendResult,
    XianyuDeliveryExecutionRecord,
    XianyuDeliveryRule,
    XianyuDeliveryRuleCreateRequest,
    XianyuDeliveryRuleUpdateRequest,
    XianyuDeliveryRuntimeStatus,
    XianyuDetailAttribute,
    XianyuFilterGroup,
    XianyuFilterOption,
    XianyuItemDetail,
    XianyuManageItem,
    XianyuManageItemPage,
    XianyuOrder,
    XianyuOrderPage,
    XianyuOrderShipResult,
    XianyuMonitorTask,
    XianyuMonitorTaskCreate,
    XianyuMonitorTaskUpdate,
    XianyuPublishImageUploadResult,
    XianyuPublishMeta,
    XianyuPublishSubmitResult,
    XianyuSearchItem,
    XianyuSearchRequest,
    XianyuSearchResult,
    XianyuUserProfile,
)
from xianyu_client.auth.api_login import XianyuAPILogin
from xianyu_client.cookie_store import (
    clear_xianyu_cookie_storage,
    load_xianyu_cookie_string,
    save_xianyu_cookie_string,
)

logger = logging.getLogger("xianyu.service")


class XianyuChatWsClient:
    """闲鱼聊天 WebSocket 客户端"""

    def __init__(
        self,
        ws_url: str,
        app_key: str,
        access_token: str,
        device_id: str,
        user_agent: str,
        sdk_user_agent: str,
        profile: XianyuChatProfile,
    ):
        self.ws_url = ws_url
        self.app_key = app_key
        self.access_token = access_token
        self.device_id = device_id
        self.user_agent = user_agent
        self.sdk_user_agent = sdk_user_agent
        self.profile = profile
        self.current_user_id = profile.main_user_id or profile.user_id

        self._ws = None
        self._receiver_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._push_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._push_subscribers: set[asyncio.Queue[Dict[str, Any]]] = set()

    async def connect(self, cookie: str = "") -> None:
        connect_kwargs = {
            "origin": "https://www.goofish.com",
            "open_timeout": 20,
        }
        connect_signature = inspect.signature(websockets.connect)
        header_name = "additional_headers" if "additional_headers" in connect_signature.parameters else "extra_headers"
        ws_headers = {
            "User-Agent": self.user_agent,
            "Host": "wss-goofish.dingtalk.com",
            "Connection": "Upgrade",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if cookie:
            ws_headers["Cookie"] = cookie

        try:
            self._ws = await websockets.connect(
                self.ws_url,
                **connect_kwargs,
                **{header_name: ws_headers},
            )
        except TypeError as exc:
            fallback_header = "extra_headers" if header_name == "additional_headers" else "additional_headers"
            if header_name not in str(exc):
                raise
            self._ws = await websockets.connect(
                self.ws_url,
                **connect_kwargs,
                **{fallback_header: ws_headers},
            )
        self._receiver_task = asyncio.create_task(self._receiver_loop())

        response = await self.send_rpc(
            "/reg",
            None,
            headers={
                "cache-header": "app-key token ua wv",
                "app-key": self.app_key,
                "token": self.access_token,
                "ua": self.sdk_user_agent,
                "dt": "j",
                "wv": "im:3,au:3,sy:6",
                "sync": "0,0;0;0;",
                "did": self.device_id,
            },
        )
        if response.get("code") != 200:
            import logging as _logging
            _logging.getLogger("xianyu.service").error(
                "ws /reg 鉴权失败: code=%s body=%s headers=%s did=%s token_len=%s",
                response.get("code"),
                response.get("body"),
                response.get("headers"),
                self.device_id,
                len(self.access_token or ""),
            )
            raise ValueError(self._extract_ws_error(response, "闲鱼聊天鉴权失败"))

        current_time = int(time.time() * 1000)
        await self.send_rpc(
            "/r/SyncStatus/ackDiff",
            [
                {
                    "pipeline": "sync",
                    "tooLong2Tag": "PNM,1",
                    "channel": "sync",
                    "topic": "sync",
                    "highPts": 0,
                    "pts": current_time * 1000,
                    "seq": 0,
                    "timestamp": current_time,
                }
            ],
        )
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        try:
            while self._ws:
                await asyncio.sleep(15)
                if self._ws:
                    await self.send_rpc("/!")
        except asyncio.CancelledError:
            return

    async def close(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._heartbeat_task
            self._heartbeat_task = None

        if self._receiver_task:
            self._receiver_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._receiver_task
            self._receiver_task = None

        if self._ws:
            with contextlib.suppress(Exception):
                await self._ws.close()
            self._ws = None

        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

    async def next_push(self) -> Dict[str, Any]:
        return await self._push_queue.get()

    def is_connected(self) -> bool:
        if not self._ws:
            return False

        # websockets 新旧版本的连接对象字段不完全一致：
        # - legacy protocol 有 .open / .closed
        # - newer ClientConnection 更依赖 .state / .close_code
        # 之前只读 .closed，遇到字段缺失或状态语义变化时会误判，导致切换会话时
        # 重建 WS + 重新请求 login.token，容易触发闲鱼风控。
        if self._receiver_task and self._receiver_task.done():
            return False

        closed = getattr(self._ws, "closed", None)
        if closed is not None:
            return not bool(closed)

        open_state = getattr(self._ws, "open", None)
        if open_state is not None:
            return bool(open_state)

        close_code = getattr(self._ws, "close_code", None)
        if close_code is not None:
            return False

        state = getattr(self._ws, "state", None)
        if state is not None:
            state_name = str(getattr(state, "name", "") or "").upper()
            state_text = str(state).upper()
            if state_name == "OPEN" or state_text.endswith(".OPEN") or state_text == "1":
                return True
            if state_name in {"CLOSING", "CLOSED"} or state_text.endswith((".CLOSING", ".CLOSED")) or state_text in {"2", "3"}:
                return False

        # 没有明确关闭信号时按已连接处理，避免保活中的正常连接被反复重建。
        return True

    def subscribe_pushes(self) -> asyncio.Queue[Dict[str, Any]]:
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._push_subscribers.add(queue)
        return queue

    def unsubscribe_pushes(self, queue: asyncio.Queue[Dict[str, Any]]) -> None:
        self._push_subscribers.discard(queue)

    async def send_rpc(
        self,
        lwp: str,
        body: Any = None,
        headers: Optional[Dict[str, Any]] = None,
        timeout: float = 15.0,
    ) -> Dict[str, Any]:
        if not self._ws or not self.is_connected():
            raise ValueError("闲鱼聊天链路未建立")

        mid = f"{random.randint(100, 999)}{int(time.time() * 1000)}"
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[mid] = future

        payload = {
            "lwp": lwp,
            "headers": {
                **(headers or {}),
                "mid": f"{mid} 0",
            },
        }
        if body is not None:
            payload["body"] = body

        await self._ws.send(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(mid, None)

    async def _receiver_loop(self) -> None:
        try:
            async for raw in self._ws:
                payload = json.loads(raw)
                headers = payload.get("headers") or {}
                response_mid = str(headers.get("mid") or "").split(" ")[0]

                if payload.get("code") is not None and response_mid:
                    future = self._pending.get(response_mid)
                    if future and not future.done():
                        future.set_result(payload)
                    continue

                if payload.get("lwp") and headers:
                    await self._push_queue.put(payload)
                    for subscriber in list(self._push_subscribers):
                        with contextlib.suppress(Exception):
                            subscriber.put_nowait(payload)
                    ack_headers = {
                        "mid": headers.get("mid", f"{random.randint(100, 999)}{int(time.time() * 1000)} 0"),
                        "sid": headers.get("sid", ""),
                    }
                    for key in ("app-key", "ua", "dt"):
                        if key in headers:
                            ack_headers[key] = headers[key]
                    ack = {"code": 200, "headers": ack_headers}
                    with contextlib.suppress(Exception):
                        await self._ws.send(json.dumps(ack, ensure_ascii=False, separators=(",", ":")))
        except asyncio.CancelledError:
            return
        except Exception as exc:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(exc)

    def _extract_ws_error(self, payload: Dict[str, Any], fallback: str) -> str:
        body = payload.get("body") or {}
        if isinstance(body, dict):
            for key in ("reason", "developerMessage", "code"):
                value = str(body.get(key) or "").strip()
                if value:
                    return value
        return fallback


class XianyuService:
    """闲鱼搜索代理服务"""

    _log = logging.getLogger("xianyu.service")

    search_api_name = "mtop.taobao.idlemtopsearch.pc.search"
    search_api_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/"
    detail_api_name = "mtop.taobao.idle.pc.detail"
    detail_api_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idle.pc.detail/1.0/"
    timestamp_api_url = "https://h5api.m.goofish.com/h5/mtop.taobao.mtop.common.getTimestamp/1.0/"
    index_api_url = "https://h5api.m.goofish.com/h5/mtop.gaia.nodejs.gaia.idle.data.gw.v2.index.get/1.0/"
    refresh_token_api_name = "mtop.taobao.idlemessage.pc.loginuser.get"
    refresh_token_api_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.loginuser.get/1.0/"
    user_nav_api_name = "mtop.idle.web.user.page.nav"
    user_nav_api_url = "https://h5api.m.goofish.com/h5/mtop.idle.web.user.page.nav/1.0/"
    page_head_api_name = "mtop.idle.web.user.page.head"
    page_head_api_url = "https://h5api.m.goofish.com/h5/mtop.idle.web.user.page.head/1.0/"
    manage_item_list_api_name = "mtop.idle.web.xyh.item.list"
    manage_item_list_api_url = "https://h5api.m.goofish.com/h5/mtop.idle.web.xyh.item.list/1.0/"
    item_polish_api_name = "mtop.taobao.idle.item.polish"
    item_polish_api_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idle.item.polish/1.0/"
    merchant_order_list_api_name = "mtop.taobao.idle.trade.merchant.sold.get"
    merchant_order_list_api_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idle.trade.merchant.sold.get/1.0/"
    merchant_order_ship_api_name = "mtop.taobao.idle.logistic.consign.dummy"
    merchant_order_ship_api_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idle.logistic.consign.dummy/1.0/"
    merchant_order_referer = "https://seller.goofish.com/?site=COMMONPRO#/seller-trade/order-manage"
    merchant_order_biz_code = "COMMONPRO"
    chat_login_user_api_name = "mtop.taobao.idlemessage.pc.loginuser.get"
    chat_login_user_api_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.loginuser.get/1.0/"
    chat_user_query_api_name = "mtop.taobao.idlemessage.pc.user.query"
    chat_user_query_api_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.user.query/1.0/"
    chat_login_token_api_name = "mtop.taobao.idlemessage.pc.login.token"
    chat_login_token_api_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.login.token/1.0/"
    chat_ws_url = "wss://wss-goofish.dingtalk.com/"
    chat_ws_app_key = "444e9908a51d1cb236a27862abc769c9"
    chat_domain = "goofish"
    chat_message_start_cursor = "9007199254740991"
    chat_sdk_version = "2.1.5"
    app_key = "34839810"

    default_headers = {
        "accept": "application/json",
        "accept-language": "en,zh-CN;q=0.9,zh;q=0.8",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.goofish.com",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://www.goofish.com/",
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self):
        config_dir = get_runtime_config_dir()
        self._monitor_store_path = config_dir / "xianyu_monitor_tasks.json"
        self._xianyu_cookie_path = config_dir / "xianyu_cookies.json"
        self._chat_ai_config_path = config_dir / "xianyu_ai_config.json"
        self._chat_ai_sessions_path = config_dir / "xianyu_ai_sessions.json"
        self._chat_device_store_path = config_dir / "xianyu_chat_devices.json"
        self._item_store_path = config_dir / "xianyu_manage_items.json"
        self._delivery_rules_path = config_dir / "xianyu_delivery_rules.json"
        self._delivery_runtime_path = config_dir / "xianyu_delivery_runtime.json"
        self._browser_login_manager = XianyuBrowserLoginManager(config_dir)
        self._monitor_store: XianyuMonitorStore | None = None
        self._chat_ai_store: XianyuChatAiStore | None = None
        self._item_store: XianyuItemStore | None = None
        self._delivery_store: XianyuDeliveryStore | None = None
        self._delivery_runtime: XianyuDeliveryRuntime | None = None
        self._delivery_runtime_running_state: bool = False
        self._temp_provider_api_key: str | None = None
        self._monitor_runner_task: asyncio.Task | None = None
        self._auth_login: XianyuAPILogin | None = None
        self._current_qr_payload: dict[str, str] | None = None
        self._processed_ai_message_keys = deque(maxlen=1000)
        self._processed_ai_message_set: set[str] = set()
        # 后台 chat AI listener / 保活 / 共享 ws
        self._shared_chat_client: XianyuChatWsClient | None = None
        self._shared_chat_client_lock = asyncio.Lock()
        self._chat_ai_listener_task: asyncio.Task | None = None
        self._chat_ai_listener_lock = asyncio.Lock()
        self._chat_keepalive_task: asyncio.Task | None = None
        self._chat_keepalive_lock = asyncio.Lock()
        self.chat_keepalive_interval_seconds: int = 180
        # 买家信息缓存（避免每次拉会话列表都并发请求 mtop.idle.web.user.page.head 触发风控）
        self._peer_info_cache: dict[str, dict] = {}
        self._peer_info_cache_ts: dict[str, float] = {}
        self._peer_info_cache_ttl: float = 300.0  # 5 分钟
        self._chat_session_info_cache: dict[str, dict] = {}
        self._chat_session_info_cache_ts: dict[str, float] = {}
        self._chat_session_info_cache_ttl: float = 300.0  # 5 分钟
        self._peer_info_semaphore = asyncio.Semaphore(3)  # 同时最多 3 个并发
        self._chat_session_info_semaphore = asyncio.Semaphore(2)
        self._conversation_item_cache: dict[str, dict[str, str]] = {}
        # login.token 熔断器：连续 N 次 FAIL_SYS_USER_VALIDATE 后暂停一段时间不再请求
        self._login_token_fail_count: int = 0
        self._login_token_block_until: float = 0.0
        self._login_token_fail_threshold: int = 3
        self._login_token_block_seconds: float = 300.0  # 5 分钟

    @property
    def monitor_store(self) -> XianyuMonitorStore:
        if self._monitor_store is None:
            self._monitor_store = XianyuMonitorStore(self._monitor_store_path)
        return self._monitor_store

    def _get_xianyu_cookie_value(self) -> str:
        cookie_string = load_xianyu_cookie_string()
        if cookie_string:
            return cookie_string
        return (app_settings.cookies.xianyu or "").strip()

    @property
    def auth_login(self) -> XianyuAPILogin:
        if self._auth_login is None:
            self._auth_login = XianyuAPILogin(timeout=300)
        return self._auth_login


    @property
    def chat_ai_store(self) -> XianyuChatAiStore:
        if self._chat_ai_store is None:
            self._chat_ai_store = XianyuChatAiStore(
                config_path=self._chat_ai_config_path,
                sessions_path=self._chat_ai_sessions_path,
            )
        return self._chat_ai_store

    @property
    def item_store(self) -> XianyuItemStore:
        if self._item_store is None:
            self._item_store = XianyuItemStore(self._item_store_path)
        return self._item_store

    @property
    def delivery_store(self) -> XianyuDeliveryStore:
        if self._delivery_store is None:
            self._delivery_store = XianyuDeliveryStore(
                rules_path=self._delivery_rules_path,
                runtime_path=self._delivery_runtime_path,
            )
        return self._delivery_store

    @property
    def delivery_runtime(self) -> XianyuDeliveryRuntime:
        if self._delivery_runtime is None:
            self._delivery_runtime = XianyuDeliveryRuntime(
                item_store=self.item_store,
                delivery_store=self.delivery_store,
            )
        return self._delivery_runtime

    async def on_xianyu_cookie_updated(self) -> None:
        """Cookie 更新后，关闭旧的共享 ws 并重启后台 listener / 保活，让它们用新 cookie 重新建立连接。"""
        # 清空临时凭据缓存
        self._temp_provider_api_key = None
        self._login_token_fail_count = 0
        self._login_token_block_until = 0.0
        # 关掉旧 ws，listener 循环里会自动用新 cookie 重连
        await self._close_shared_chat_client()
        # 先停后启，确保用新 cookie 起新连接
        await self.stop_chat_ai_listener()
        await self.stop_chat_keepalive()
        if self._should_run_chat_event_listener():
            await self.ensure_chat_ai_listener()
        if self._should_run_chat_keepalive():
            await self.ensure_chat_keepalive()

    def _should_run_chat_ai_listener(self) -> bool:
        config = self.get_chat_ai_config()
        if not config.enabled:
            return False
        if not self._get_xianyu_cookie_value():
            return False
        if not self.chat_ai_store.get_active_provider():
            return False
        return True

    def _should_run_chat_event_listener(self) -> bool:
        """只要 Cookie 配置好就维护后台共享 ws；AI 自动回复在循环内部按 config.enabled 过滤。

        这样所有 HTTP 路由（list_chat_messages、send_chat_text 等）都能复用这个共享连接，
        避免每次请求都新开 ws + 调 login.token，触发闲鱼风控（FAIL_SYS_USER_VALIDATE）。
        """
        return bool(self._get_xianyu_cookie_value())

    def _should_run_chat_keepalive(self) -> bool:
        return bool(self._get_xianyu_cookie_value())

    def _sync_chat_ai_listener_state(self) -> None:
        """根据当前 AI 配置 / Cookie / Provider 启停后台 listener 与保活。"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        if self._should_run_chat_event_listener():
            loop.create_task(self.ensure_chat_ai_listener())
        else:
            loop.create_task(self.stop_chat_ai_listener())

        if self._should_run_chat_keepalive():
            loop.create_task(self.ensure_chat_keepalive())
        else:
            loop.create_task(self.stop_chat_keepalive())

    async def ensure_chat_ai_listener(self) -> bool:
        if not self._should_run_chat_event_listener():
            return False

        async with self._chat_ai_listener_lock:
            if self._chat_ai_listener_task and not self._chat_ai_listener_task.done():
                return True
            self._chat_ai_listener_task = asyncio.create_task(
                self._chat_ai_listener_loop(),
                name="xianyu-chat-ai-listener",
            )
            return True

    async def stop_chat_ai_listener(self) -> None:
        async with self._chat_ai_listener_lock:
            task = self._chat_ai_listener_task
            self._chat_ai_listener_task = None
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def ensure_chat_keepalive(self) -> bool:
        if not self._should_run_chat_keepalive():
            return False

        async with self._chat_keepalive_lock:
            if self._chat_keepalive_task and not self._chat_keepalive_task.done():
                return True
            self._chat_keepalive_task = asyncio.create_task(
                self._chat_keepalive_loop(),
                name="xianyu-chat-keepalive",
            )
            return True

    async def stop_chat_keepalive(self) -> None:
        async with self._chat_keepalive_lock:
            task = self._chat_keepalive_task
            self._chat_keepalive_task = None
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def _close_shared_chat_client(self) -> None:
        async with self._shared_chat_client_lock:
            stale_client = self._shared_chat_client
            self._shared_chat_client = None
        if stale_client:
            with contextlib.suppress(Exception):
                await stale_client.close()

    async def _refresh_chat_runtime_token(self) -> None:
        cookie = self._require_xianyu_cookie()
        async with self._create_http_client(cookie) as client:
            await self._refresh_login_state(client)

    async def _chat_keepalive_tick(self) -> bool:
        if not self._should_run_chat_keepalive():
            return False
        await self._refresh_chat_runtime_token()
        shared_client = self._shared_chat_client
        if shared_client and not shared_client.is_connected():
            await self._close_shared_chat_client()
        return True

    async def _chat_keepalive_loop(self) -> None:
        try:
            while True:
                if not self._should_run_chat_keepalive():
                    await asyncio.sleep(1.0)
                    continue
                try:
                    await self._chat_keepalive_tick()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning(f"闲鱼聊天保活失败，将稍后重试: {exc}")
                await asyncio.sleep(self.chat_keepalive_interval_seconds)
        except asyncio.CancelledError:
            logger.info("闲鱼聊天保活已停止")
            raise

    async def _chat_ai_listener_loop(self) -> None:
        subscriber: asyncio.Queue[Dict[str, Any]] | None = None
        chat_client: XianyuChatWsClient | None = None
        last_refresh_at = time.monotonic()
        consecutive_failures = 0

        try:
            while True:
                if not self._should_run_chat_event_listener():
                    await asyncio.sleep(1.0)
                    consecutive_failures = 0
                    continue

                try:
                    chat_client = await self.open_chat_ws_client()
                    async with self._shared_chat_client_lock:
                        self._shared_chat_client = chat_client
                    subscriber = chat_client.subscribe_pushes()
                    logger.info("闲鱼聊天 AI 后台监听已启动")

                    while True:
                        if not self._should_run_chat_event_listener():
                            break
                        if not chat_client.is_connected():
                            raise ConnectionError("闲鱼聊天共享连接已断开")

                        if time.monotonic() - last_refresh_at >= 600:
                            with contextlib.suppress(Exception):
                                await self._refresh_chat_runtime_token()
                            last_refresh_at = time.monotonic()

                        try:
                            payload = await asyncio.wait_for(subscriber.get(), timeout=15.0)
                        except asyncio.TimeoutError:
                            if not chat_client.is_connected():
                                raise ConnectionError("闲鱼聊天共享连接已断开")
                            continue

                        consecutive_failures = 0
                        decoded = self.decode_chat_push(payload)
                        items_count = len(decoded.get("items") or [])
                        biz_types = [it.get("biz_type") for it in (decoded.get("items") or [])]
                        logger.info(f"AI 监听收到推送: type={decoded.get('type')} items={items_count} biz_types={biz_types}")
                        delivery_event = self._extract_delivery_candidate_event(decoded, profile=chat_client.profile)
                        if delivery_event:
                            try:
                                await self.handle_delivery_candidate_event(delivery_event)
                            except Exception as exc:
                                logger.warning(f"闲鱼自动发货事件处理失败: {exc}")
                        try:
                            await self.maybe_auto_reply_from_decoded_push(chat_client.profile, decoded)
                        except Exception as exc:
                            logger.warning(f"闲鱼聊天 AI 自动回复失败: {exc}")
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    consecutive_failures += 1
                    base_delay = min(5 * (2 ** (consecutive_failures - 1)), 60)
                    delay = base_delay + random.uniform(0, base_delay * 0.3)
                    logger.warning(
                        f"闲鱼聊天 AI 后台监听异常，{delay:.0f} 秒后重连 (连续失败 {consecutive_failures} 次): {exc}"
                    )
                    await self._close_shared_chat_client()
                    await asyncio.sleep(delay)
                finally:
                    if chat_client and subscriber:
                        chat_client.unsubscribe_pushes(subscriber)
                    subscriber = None
                    chat_client = None
        except asyncio.CancelledError:
            logger.info("闲鱼聊天 AI 后台监听已停止")
            raise

    def get_chat_ai_config(self) -> XianyuChatAiConfig:
        config = self.chat_ai_store.load_config()
        self.chat_keepalive_interval_seconds = max(30, min(int(config.chat_keepalive_interval_seconds or 180), 3600))
        return config

    def set_chat_ai_enabled(self, enabled: bool) -> XianyuChatAiConfig:
        config = self.chat_ai_store.set_enabled(enabled)
        self._sync_chat_ai_listener_state()
        return config

    def set_chat_keepalive_interval(self, seconds: int) -> XianyuChatAiConfig:
        config = self.chat_ai_store.set_chat_keepalive_interval_seconds(seconds)
        self._sync_chat_ai_listener_state()
        return config

    def update_chat_ai_config(self, request: XianyuChatAiConfigUpdateRequest) -> XianyuChatAiConfig:
        """兼容旧版单供应商 AI 配置接口。"""
        config = self.chat_ai_store.save_config(request)
        self._sync_chat_ai_listener_state()
        return config

    def create_chat_ai_provider(self, request: XianyuChatAiProviderCreateRequest) -> XianyuChatAiProvider:
        provider = self.chat_ai_store.create_provider(request)
        self._sync_chat_ai_listener_state()
        return provider

    def update_chat_ai_provider(self, provider_id: str, request: XianyuChatAiProviderUpdateRequest) -> XianyuChatAiProvider | None:
        provider = self.chat_ai_store.update_provider(provider_id, request)
        self._sync_chat_ai_listener_state()
        return provider

    def delete_chat_ai_provider(self, provider_id: str) -> bool:
        deleted = self.chat_ai_store.delete_provider(provider_id)
        self._sync_chat_ai_listener_state()
        return deleted

    def set_active_chat_ai_provider(self, provider_id: str) -> bool:
        activated = self.chat_ai_store.set_active_provider(provider_id)
        self._sync_chat_ai_listener_state()
        return activated

    def _load_secret_chat_ai_api_key(self) -> str:
        provider = self.chat_ai_store.get_active_provider()
        if not provider:
            return ""
        return self.chat_ai_store.load_secret_api_key(provider.id).strip()

    def list_chat_ai_session_states(self, cids: list[str]) -> list[Any]:
        return self.chat_ai_store.list_session_states(cids)

    def set_chat_ai_session_state(self, cid: str, enabled: bool):
        return self.chat_ai_store.set_session_enabled(cid, enabled)

    async def test_chat_ai_reply(self, text: str, cid: str = "") -> str:
        provider = self.chat_ai_store.get_active_provider()
        if not provider:
            raise ValueError("尚未配置 AI 供应商")
        messages = self._build_chat_ai_messages(provider=provider, text=text, cid=cid)
        return await self._request_chat_ai_reply(provider=provider, messages=messages)

    async def test_chat_ai_provider(
        self,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        text: str = "你好，请简单介绍一下你自己。",
    ) -> str:
        if not api_key:
            raise ValueError("API Key 不能为空")
        if not base_url:
            raise ValueError("Base URL 不能为空")
        if not model:
            raise ValueError("模型名称不能为空")

        temp_provider = XianyuChatAiProvider(
            id="test",
            name="测试供应商",
            base_url=base_url.rstrip("/"),
            models=[model],
            active_model=model,
            system_prompt=system_prompt or "你是闲鱼客服助手，回复要简洁、礼貌、像真人卖家。",
            api_key_configured=True,
            api_key_masked="",
            is_active=True,
        )
        self._temp_provider_api_key = api_key
        try:
            messages = self._build_chat_ai_messages(provider=temp_provider, text=text, cid="")
            return await self._request_chat_ai_reply(provider=temp_provider, messages=messages)
        finally:
            self._temp_provider_api_key = None

    def _build_qrcode_data_url(self, content: str) -> str | None:
        try:
            image = qrcode.make(content, image_factory=qrcode.image.svg.SvgImage)
            buffer = io.BytesIO()
            image.save(buffer)
            encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return f"data:image/svg+xml;base64,{encoded}"
        except Exception:
            return None

    async def _browser_login_qrcode_data_url(self, page) -> str:
        """从浏览器登录页提取二维码 data URL。

        优先读取 canvas.toDataURL；如果二维码 canvas 被跨域图片污染导致 tainted，
        只截取 canvas 元素本身，避免退化为整页截图。
        """
        canvas = page.locator("canvas")
        canvas_count = 0
        with contextlib.suppress(Exception):
            canvas_count = int(await canvas.count())

        if canvas_count > 0:
            with contextlib.suppress(Exception):
                data_url = await page.evaluate(
                    """selector => {
                        const canvas = document.querySelector(selector);
                        return canvas ? canvas.toDataURL('image/png') : '';
                    }""",
                    "canvas",
                )
                if isinstance(data_url, str) and data_url.startswith("data:image/"):
                    return data_url

            screenshot_bytes = await canvas.first.screenshot(type="png")
            encoded = base64.b64encode(screenshot_bytes).decode("utf-8")
            return f"data:image/png;base64,{encoded}"

        for selector in ("img[src^='data:image']", "img"):
            locator = page.locator(selector)
            count = 0
            with contextlib.suppress(Exception):
                count = int(await locator.count())
            if count <= 0:
                continue
            with contextlib.suppress(Exception):
                src = str(await locator.first.get_attribute("src") or "").strip()
                if src.startswith("data:image/"):
                    return src
            screenshot_bytes = await locator.first.screenshot(type="png")
            encoded = base64.b64encode(screenshot_bytes).decode("utf-8")
            return f"data:image/png;base64,{encoded}"

        raise ValueError("未找到扫码二维码")

    def _browser_login_cookie_string(self, cookies: list[dict[str, Any]]) -> str:
        """保留 goofish 相关 Cookie，避免遗漏 havana/cookie2/_m_h5_tk 等登录态。"""
        result: dict[str, str] = {}
        for cookie in cookies or []:
            name = str(cookie.get("name") or "").strip()
            value = str(cookie.get("value") or "")
            domain = str(cookie.get("domain") or "").lower()
            if not name:
                continue
            if "goofish.com" in domain or "taobao.com" in domain or "alibaba.com" in domain:
                result[name] = value
        return "; ".join(f"{name}={value}" for name, value in result.items())

    async def _browser_login_status_from_page(self, page, context) -> dict[str, Any]:
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("domcontentloaded", timeout=1000)
        with contextlib.suppress(Exception):
            await page.wait_for_timeout(300)

        cookies = await context.cookies()
        cookie_string = self._browser_login_cookie_string(cookies)
        cookie_names = {str(cookie.get("name") or "") for cookie in cookies or []}
        has_login_cookie = any(
            name.startswith("havana_lgc2_")
            or name in {"unb", "cookie2", "cookie17", "sgcookie", "tracknick"}
            for name in cookie_names
        )
        if cookie_string and has_login_cookie:
            return {
                "success": True,
                "message": "登录成功",
                "status": "success",
                "is_logged_in": True,
                "login_token": cookie_string,
                "cookie_string": cookie_string,
            }

        text = ""
        with contextlib.suppress(Exception):
            text = str(await page.evaluate("document.body ? document.body.innerText : ''") or "")
        if "已扫码" in text or "确认" in text:
            return {"success": True, "message": "已扫码，请在手机上确认登录", "status": "scanned", "is_logged_in": False}
        return {"success": True, "message": "等待扫码中...", "status": "waiting", "is_logged_in": False}

    async def start_browser_login(self) -> dict[str, Any]:
        """启动真实浏览器扫码登录；Playwright 不可用时返回清晰失败信息。"""
        try:
            from playwright.async_api import async_playwright

            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=self.default_headers["user-agent"])
            page = await context.new_page()
            await page.goto("https://passport.goofish.com/mini_login.htm", wait_until="domcontentloaded")
            qrcode_image = await self._browser_login_qrcode_data_url(page)
            session = self._browser_login_manager.create_session(qrcode_image=qrcode_image, expires_in=300)

            async def cleanup():
                with contextlib.suppress(Exception):
                    await context.close()
                with contextlib.suppress(Exception):
                    await browser.close()
                with contextlib.suppress(Exception):
                    await playwright.stop()

            async def monitor_login():
                try:
                    while True:
                        manager_session = self._browser_login_manager.get_session(session.session_id)
                        if not manager_session or manager_session.status in {"success", "cancelled", "expired", "failed"}:
                            break
                        status = await self._browser_login_status_from_page(page, context)
                        if status.get("is_logged_in"):
                            cookie_string = str(status.get("cookie_string") or status.get("login_token") or "")
                            if cookie_string:
                                self._browser_login_manager.mark_success(session.session_id, cookie_string=cookie_string)
                                app_settings.cookies.xianyu = cookie_string
                                await self.on_xianyu_cookie_updated()
                                break
                        else:
                            self._browser_login_manager.update_session(
                                session.session_id,
                                status=str(status.get("status") or "waiting"),
                                message=str(status.get("message") or "等待扫码中..."),
                            )
                        await asyncio.sleep(2)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    with contextlib.suppress(Exception):
                        self._browser_login_manager.update_session(
                            session.session_id,
                            status="failed",
                            message=f"浏览器扫码登录失败: {exc}",
                        )
                finally:
                    await cleanup()

            monitor_task = asyncio.create_task(monitor_login(), name=f"xianyu-browser-login-{session.session_id}")
            self._browser_login_manager.bind_runtime(session.session_id, cleanup=cleanup, monitor_task=monitor_task)
            return {
                "success": True,
                "message": session.message,
                "session_id": session.session_id,
                "qrcode_image": session.qrcode_image,
                "expires_in": max(session.expires_at - int(time.time()), 0),
            }
        except Exception as exc:
            return {
                "success": False,
                "message": f"启动浏览器扫码登录失败: {exc}",
                "session_id": "",
                "qrcode_image": None,
                "expires_in": 0,
            }

    async def get_browser_login_status(self, session_id: str) -> dict[str, Any]:
        session = self._browser_login_manager.get_session(session_id)
        if not session:
            return {
                "success": False,
                "message": "扫码会话不存在或已失效",
                "status": "expired",
                "is_logged_in": False,
                "login_token": None,
            }
        return {
            "success": True,
            "message": session.message,
            "status": session.status,
            "is_logged_in": session.status == "success",
            "login_token": session.login_token or None,
        }

    async def cancel_browser_login(self, session_id: str) -> dict[str, Any]:
        try:
            return self._browser_login_manager.cancel_session(session_id)
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    def get_login_qrcode(self) -> dict[str, Any]:
        try:
            self.auth_login.init_login_page()
            qr_token, qr_url = self.auth_login.get_qr_code()
            device_id = self.auth_login.client.cookies.get("cna", "") or self.auth_login._cna or ""
            page_trace_id = self.auth_login._generate_page_trace_id()
            self._current_qr_payload = {
                "qrcode_token": qr_token,
                "device_id": device_id,
                "page_trace_id": page_trace_id,
            }
            return {
                "success": True,
                "message": "二维码已生成，请使用闲鱼 APP 扫码",
                "qrcode_url": qr_url,
                "qrcode_token": qr_token,
                "qrcode_image": self._build_qrcode_data_url(qr_url),
            }
        except Exception as exc:
            return {
                "success": False,
                "message": f"获取二维码失败: {exc}",
            }

    def check_login_status(self, qrcode_token: str) -> dict[str, Any]:
        try:
            if not self._current_qr_payload or self._current_qr_payload.get("qrcode_token") != qrcode_token:
                return {
                    "success": False,
                    "message": "二维码已过期，请重新获取",
                    "is_logged_in": False,
                }

            result = self.auth_login.query_qrcode(
                t=qrcode_token,
                device_id=self._current_qr_payload["device_id"],
                page_trace_id=self._current_qr_payload["page_trace_id"],
            )
            qr_data = result.get("content", {}).get("data", {})
            qr_status = str(qr_data.get("qrCodeStatus") or "").upper()

            if qr_status in {"", "NEW"}:
                return {"success": True, "message": "等待扫码...", "is_logged_in": False}
            if qr_status == "SCANED":
                return {"success": True, "message": "已扫码，请在手机上确认登录", "is_logged_in": False}
            if qr_status != "CONFIRMED":
                return {"success": False, "message": f"未知登录状态: {qr_status}", "is_logged_in": False}

            confirm_url = (
                qr_data.get("feedbackPayload", {})
                .get("dynamicUrl", {})
                .get("dialogConfirmLoginUrl", "")
            )
            if not confirm_url or "token=" not in confirm_url:
                return {"success": False, "message": "缺少确认登录链接", "is_logged_in": False}

            token = confirm_url.split("token=", 1)[1].split("&", 1)[0]
            self.auth_login.confirm_login(
                token=token,
                device_id=self._current_qr_payload["device_id"],
                page_trace_id=self._current_qr_payload["page_trace_id"],
            )
            with contextlib.suppress(Exception):
                self.auth_login.query_login_settings()
            with contextlib.suppress(Exception):
                self.auth_login.silent_has_login()
            with contextlib.suppress(Exception):
                self.auth_login.client.get("https://www.goofish.com/", timeout=15)

            cookie_string = self.auth_login.extract_xianyu_cookie_string()
            if not cookie_string:
                return {"success": False, "message": "扫码成功但未获取到 Cookie", "is_logged_in": False}

            save_xianyu_cookie_string(cookie_string, source="qrcode_login")
            app_settings.cookies.xianyu = cookie_string
            return {
                "success": True,
                "message": "登录成功",
                "is_logged_in": True,
                "login_token": cookie_string,
            }
        except Exception as exc:
            return {
                "success": False,
                "message": f"检查登录状态失败: {exc}",
                "is_logged_in": False,
            }

    def login(self, method: str = "cookie", cookies: str | None = None) -> dict[str, Any]:
        if method == "qrcode":
            return self.get_login_qrcode()

        cookie_string = str(cookies or "").strip()
        if not cookie_string:
            return {"success": False, "message": "Cookie 不能为空"}

        save_xianyu_cookie_string(cookie_string, source="manual_input")
        app_settings.cookies.xianyu = cookie_string
        return {
            "success": True,
            "message": "Cookie 登录成功",
            "cookies": cookie_string,
        }

    async def get_auth_status(self) -> dict[str, Any]:
        cookie_string = self._get_xianyu_cookie_value()
        if not cookie_string:
            return {"success": True, "message": "", "is_logged_in": False, "user_info": None}

        try:
            profile = await self.get_user_profile()
            user_info = profile.model_dump()
            return {"success": True, "message": "", "is_logged_in": True, "user_info": user_info}
        except Exception:
            return {"success": True, "message": "", "is_logged_in": False, "user_info": None}

    def logout(self) -> dict[str, Any]:
        clear_xianyu_cookie_storage()
        app_settings.cookies.xianyu = ""
        self._current_qr_payload = None
        return {"success": True, "message": "已退出登录"}

    def list_monitor_tasks(self) -> list[XianyuMonitorTask]:
        return self.monitor_store.list_tasks()

    def get_monitor_task(self, task_id: str) -> XianyuMonitorTask:
        for task in self.list_monitor_tasks():
            if task.id == task_id:
                return task
        raise ValueError("监控任务不存在")

    def create_monitor_task(self, request: XianyuMonitorTaskCreate) -> XianyuMonitorTask:
        return self.monitor_store.create_task(request)

    def create_monitor_task_from_payload(self, payload: dict[str, Any]) -> XianyuMonitorTask:
        return self.create_monitor_task(XianyuMonitorTaskCreate(**payload))

    def update_monitor_task(self, task_id: str, request: XianyuMonitorTaskUpdate) -> XianyuMonitorTask:
        updated = self.monitor_store.update_task(task_id, request.model_dump(exclude_none=True))
        if updated is None:
            raise ValueError("监控任务不存在")
        return updated

    def delete_monitor_task(self, task_id: str) -> bool:
        return self.monitor_store.delete_task(task_id)

    def toggle_monitor_task(self, task_id: str) -> XianyuMonitorTask:
        task = self.get_monitor_task(task_id)
        updated = self.monitor_store.update_task(task_id, {"enabled": not task.enabled})
        if updated is None:
            raise ValueError("监控任务不存在")
        return updated

    def get_monitor_hits(self, task_id: str):
        return self.get_monitor_task(task_id).latest_hits

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
        fresh: list[dict[str, Any]] = []
        for item in result.items:
            current = item if isinstance(item, dict) else item.model_dump()
            item_id = str(current.get("item_id") or "").strip()
            if not item_id:
                continue
            price_value = self._extract_price_number(str(current.get("price") or ""))
            if task.min_price is not None and (price_value is None or price_value < task.min_price):
                continue
            if task.max_price is not None and (price_value is None or price_value > task.max_price):
                continue
            if item_id not in seen:
                fresh.append(current)
            seen.add(item_id)

        updated = self.monitor_store.record_run(
            task_id,
            new_hits=fresh,
            seen_item_ids=list(seen),
            status="ok",
        )
        if updated is None:
            raise ValueError("监控任务不存在")
        return updated

    def _extract_price_number(self, price_text: str) -> float | None:
        match = re.search(r"\d+(?:\.\d+)?", price_text or "")
        if not match:
            return None
        try:
            return float(match.group(0))
        except ValueError:
            return None

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

    async def upload_publish_image(
        self,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> XianyuPublishImageUploadResult:
        response = await self._call_publish_image_upload_api(filename, content, content_type)
        data = response.get("data") or {}
        obj = response.get("object") or {}
        image_url = str(obj.get("url") or data.get("imageUrl") or "")
        width = 0
        height = 0
        pix = str(obj.get("pix") or "")
        if "x" in pix:
            parts = pix.split("x", 1)
            try:
                width, height = int(parts[0]), int(parts[1])
            except (ValueError, IndexError):
                pass
        if not width:
            width = int(data.get("width") or 0)
        if not height:
            height = int(data.get("height") or 0)
        return XianyuPublishImageUploadResult(
            image_id=str(data.get("imageId") or ""),
            image_url=image_url,
            width=width,
            height=height,
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

    async def _call_publish_submit_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("闲鱼发布提交接口尚未接入")

    upload_url = "https://stream-upload.goofish.com/api/upload.api"

    async def _call_publish_image_upload_api(
        self,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> dict[str, Any]:
        """上传图片到闲鱼，参照 XianYuApis 的 upload_media"""
        cookie = self._require_xianyu_cookie()
        async with self._create_http_client(cookie) as client:
            params = {
                "floderId": "0",
                "appkey": "xy_chat",
                "_input_charset": "utf-8",
            }
            files = {"file": (filename, content, content_type or "image/png")}
            response = await client.post(
                self.upload_url,
                params=params,
                files=files,
            )
            response.raise_for_status()
            return response.json()

    async def search(self, request: XianyuSearchRequest) -> XianyuSearchResult:
        """执行闲鱼搜索"""
        cookie = self._get_xianyu_cookie_value()
        if not cookie:
            raise ValueError("请先在设置页配置闲鱼 Cookie")

        async with httpx.AsyncClient(
            headers=self.default_headers,
            timeout=20.0,
            follow_redirects=True,
        ) as client:
            for name, value in self._parse_cookie_string(cookie).items():
                client.cookies.set(name, value, domain=".goofish.com")

            response_data = await self._execute_api(
                client,
                api_name=self.search_api_name,
                api_url=self.search_api_url,
                payload=self._build_payload(request),
                extra_params={
                    "spm_cnt": "a21ybx.search.0.0",
                    "spm_pre": "a21ybx.home.searchInput.0",
                },
            )
            return self._map_result(response_data, request)

    async def get_user_profile(self) -> XianyuUserProfile:
        """获取当前闲鱼登录用户信息"""
        cookie = self._get_xianyu_cookie_value()
        if not cookie:
            raise ValueError("请先在设置页配置闲鱼 Cookie")

        async with httpx.AsyncClient(
            headers=self.default_headers,
            timeout=20.0,
            follow_redirects=True,
        ) as client:
            for name, value in self._parse_cookie_string(cookie).items():
                client.cookies.set(name, value, domain=".goofish.com")

            response_data = await self._execute_api(
                client,
                api_name=self.user_nav_api_name,
                api_url=self.user_nav_api_url,
                payload={},
            )
            return self._map_user_profile(response_data)

    async def get_item_detail(self, item_id: str) -> XianyuItemDetail:
        """获取闲鱼宝贝详情"""
        cookie = self._get_xianyu_cookie_value()
        if not cookie:
            raise ValueError("请先在设置页配置闲鱼 Cookie")

        async with httpx.AsyncClient(
            headers=self.default_headers,
            timeout=20.0,
            follow_redirects=True,
        ) as client:
            for name, value in self._parse_cookie_string(cookie).items():
                client.cookies.set(name, value, domain=".goofish.com")

            if not self._get_cookie_value(client, "_m_h5_tk"):
                await self._warmup_token(client)

            await self._refresh_login_state(client)

            response_data = await self._execute_api(
                client,
                api_name=self.detail_api_name,
                api_url=self.detail_api_url,
                payload={"itemId": item_id},
                extra_params={
                    "spm_cnt": "a21ybx.item.0.0",
                    "spm_pre": "a21ybx.search.0.0",
                },
            )
            return self._map_item_detail(response_data, item_id)

    async def get_chat_profile(self) -> XianyuChatProfile:
        """获取闲鱼聊天当前账号信息"""
        cookie = self._require_xianyu_cookie()
        async with self._create_http_client(cookie) as client:
            bootstrap = await self._build_chat_bootstrap(client, include_token=False)
        return bootstrap["profile"]

    async def diagnose_chat_runtime(self) -> XianyuChatHealthStatus:
        """诊断闲鱼聊天链路状态。优先使用后台共享 ws 的连接状态。"""
        cookie_configured = bool(self._get_xianyu_cookie_value())
        shared_ws_connected = bool(self._shared_chat_client and self._shared_chat_client.is_connected())

        if not cookie_configured:
            return XianyuChatHealthStatus(
                ok=False,
                status="cookie_missing",
                message="未配置闲鱼 Cookie，请先登录后更新 Cookie。",
                shared_ws_connected=shared_ws_connected,
                cookie_configured=False,
            )

        # 后台 listener 已经维护着共享 ws，直接读其状态即可
        if shared_ws_connected:
            return XianyuChatHealthStatus(
                ok=True,
                status="ok",
                message="闲鱼聊天链路正常。",
                shared_ws_connected=True,
                cookie_configured=True,
            )

        # 共享 ws 未连接时，实际探测一次聊天 WS；否则 login.token / /reg 风控不会暴露给前端。
        probe_client = None
        try:
            probe_client = await self.open_chat_ws_client()
            return XianyuChatHealthStatus(
                ok=True,
                status="ok",
                message="闲鱼聊天链路正常。",
                shared_ws_connected=bool(probe_client and probe_client.is_connected()),
                cookie_configured=True,
            )
        except Exception as exc:
            error_text = str(exc)
            status = "error"
            captcha_url = self._extract_first_url(error_text)
            lowered = error_text.lower()
            if "captcha" in lowered or "风控" in error_text or "verify" in lowered or "validate" in lowered:
                status = "risk_blocked"
                message = f"闲鱼请求被风控拦截：{error_text}"
            elif "session_expired" in lowered or "auth" in lowered or "token" in lowered or "登录" in error_text or "鉴权" in error_text:
                status = "auth_invalid"
                message = error_text if "闲鱼" in error_text else f"闲鱼登录态可能已失效：{error_text}"
            else:
                message = f"聊天链路诊断失败：{error_text}"
            return XianyuChatHealthStatus(
                ok=False,
                status=status,
                message=message,
                captcha_url=captcha_url,
                shared_ws_connected=False,
                cookie_configured=True,
            )

    async def list_chat_conversations(self, offset: int = 0, limit: int = 20) -> XianyuChatConversationPage:
        """获取聊天会话列表"""
        async with self._borrow_chat_ws_client() as chat_client:
            response = await chat_client.send_rpc("/r/Conversation/listNewest", [offset, limit])
            self._ensure_chat_rpc_success(response, "获取闲鱼聊天会话失败")
            raw_items = [item for item in (response.get("body") or []) if isinstance(item, dict)]
            peer_info_cache: Dict[str, Dict[str, Any]] = {}
            if raw_items:
                peer_ids = set()
                session_ids = set()
                for item in raw_items:
                    single = item.get("singleChatUserConversation") or {}
                    conversation = single.get("singleChatConversation") or {}
                    ext = conversation.get("extension") or {}
                    cid = str(conversation.get("cid") or "")
                    session_id = cid.split("@", 1)[0] if cid else ""
                    if session_id:
                        session_ids.add(session_id)
                    pair_first = str(conversation.get("pairFirst") or "")
                    pair_second = str(conversation.get("pairSecond") or "")
                    current_user_id = chat_client.profile.main_user_id or chat_client.profile.user_id
                    pair_first_id = pair_first.split("@")[0] if pair_first else ""
                    pair_second_id = pair_second.split("@")[0] if pair_second else ""
                    if current_user_id and pair_first_id == current_user_id:
                        pid = pair_second_id
                    elif current_user_id and pair_second_id == current_user_id:
                        pid = pair_first_id
                    else:
                        pid = str(ext.get("extUserId") or pair_second_id or pair_first_id)
                    if pid and pid not in {"0", "-1"}:
                        peer_ids.add(pid)
                if session_ids:
                    tasks = [self.get_chat_session_user_info(session_id) for session_id in session_ids]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for session_id, result in zip(session_ids, results):
                        if isinstance(result, dict) and result:
                            peer_info_cache[session_id] = result
                if peer_ids:
                    tasks = [self.get_peer_user_info(pid) for pid in peer_ids]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for pid, result in zip(peer_ids, results):
                        if isinstance(result, dict) and result:
                            peer_info_cache[pid] = result
            conversations = [
                self._map_chat_conversation(item, chat_client.profile, peer_info_cache)
                for item in raw_items
            ]
            return XianyuChatConversationPage(
                total=len(conversations),
                offset=offset,
                limit=limit,
                conversations=conversations,
            )

    async def list_chat_messages(
        self,
        cid: str,
        cursor: str | None = None,
        limit: int = 20,
        direction: str = "prev",
    ) -> XianyuChatMessagePage:
        """获取聊天消息列表"""
        async with self._borrow_chat_ws_client() as chat_client:
            response = await chat_client.send_rpc(
                "/r/MessageManager/listUserMessages",
                [
                    cid,
                    direction == "next",
                    self._normalize_message_cursor(cursor),
                    limit,
                    False,
                ],
            )
            self._ensure_chat_rpc_success(response, "获取闲鱼聊天消息失败")

            payload = response.get("body") or {}
            raw_messages = payload.get("userMessageModels") or []
            messages = [
                self._map_chat_message(item, cid, chat_client.profile)
                for item in raw_messages
                if isinstance(item, dict)
            ]
            messages.sort(key=lambda item: item.create_at)

            next_cursor = payload.get("nextCursor")
            return XianyuChatMessagePage(
                cid=cid,
                cursor=str(next_cursor) if next_cursor not in (None, "") else None,
                has_more=bool(payload.get("hasMore")),
                messages=messages,
            )

    async def send_chat_text(self, cid: str, text: str) -> XianyuChatSendResult:
        """发送闲鱼聊天文本消息"""
        summary = text.strip()
        if not summary:
            raise ValueError("请输入要发送的消息内容")

        async with self._borrow_chat_ws_client() as chat_client:
            conversation_payload = await self._get_chat_conversation_payload(chat_client, cid)
            message_payload, send_options = self._build_chat_send_payloads(
                cid=cid,
                text=summary,
                conversation_payload=conversation_payload,
                profile=chat_client.profile,
            )

            response: Dict[str, Any] | None = None
            retryable_messages = {"system is error", "闲鱼走神了，您稍后再试～"}
            fallback_options = self._build_chat_send_option_fallbacks(send_options)

            last_error: ValueError | None = None
            for index, option_payload in enumerate(fallback_options):
                response = await chat_client.send_rpc(
                    "/r/MessageSend/sendByReceiverScope",
                    [message_payload, option_payload],
                )
                try:
                    self._ensure_chat_rpc_success(response, "发送闲鱼聊天消息失败")
                    break
                except ValueError as exc:
                    last_error = exc
                    message = str(exc).strip()
                    is_last = index >= len(fallback_options) - 1
                    if is_last or message not in retryable_messages:
                        raise
            if response is None:
                if last_error:
                    raise last_error
                raise ValueError("发送闲鱼聊天消息失败")

            return self._build_chat_send_result(cid=cid, summary=summary, payload=response)

    async def clear_chat_red_point(self, cids: List[str]) -> XianyuChatClearResult:
        """清理聊天会话红点"""
        valid_cids = [cid for cid in cids if cid]
        if not valid_cids:
            return XianyuChatClearResult(success_count=0)

        async with self._borrow_chat_ws_client() as chat_client:
            response = await chat_client.send_rpc("/r/Conversation/clearRedPoint", [valid_cids])
            try:
                self._ensure_chat_rpc_success(response, "清理闲鱼聊天红点失败")
            except ValueError as exc:
                message = str(exc).strip()
                if message in {"system is error", "闲鱼走神了，您稍后再试～"}:
                    return XianyuChatClearResult(success_count=0)
                raise
            return XianyuChatClearResult(success_count=len(valid_cids))

    async def send_chat_image(self, cid: str, image_url: str, width: int = 0, height: int = 0) -> XianyuChatSendResult:
        """发送闲鱼聊天图片消息，参照 XianYuApis 的 send_image，含 fallback 重试"""
        async with self._borrow_chat_ws_client() as chat_client:
            image_base64 = self._encode_chat_image(image_url, width, height)
            msg_payload = {
                "uuid": self._generate_message_uuid(),
                "cid": cid,
                "conversationType": 1,
                "content": {"contentType": 101, "custom": {"type": 2, "data": image_base64}},
                "redPointPolicy": 0,
                "extension": {"extJson": "{}"},
                "ctx": {"appVersion": "1.0", "platform": "web"},
                "mtags": {},
                "msgReadStatusSetting": 1,
            }
            conversation_payload = await self._get_chat_conversation_payload(chat_client, cid)
            single = conversation_payload.get("singleChatUserConversation") or {}
            conversation = single.get("singleChatConversation") or {}
            pair_first = self._normalize_chat_uid(str(conversation.get("pairFirst") or ""))
            pair_second = self._normalize_chat_uid(str(conversation.get("pairSecond") or ""))
            current_user_id = str(chat_client.profile.main_user_id or chat_client.profile.user_id or "")
            current_uid = self._normalize_chat_uid(current_user_id)
            pair_first_id = pair_first.split("@", 1)[0] if pair_first else ""
            pair_second_id = pair_second.split("@", 1)[0] if pair_second else ""
            receiver_uid = pair_second if pair_first_id == current_user_id else pair_first
            receivers = [receiver_uid] if receiver_uid else []

            full_send_options = {
                "actualReceivers": [f"{r}@goofish" if "@" not in r else r for r in receivers],
                "createSingleChatCoversation": {
                    "cid": cid,
                    "pairFirst": pair_first,
                    "pairSecond": pair_second,
                    "bizType": str(conversation.get("bizType") or ""),
                    "extension": {
                        key: str(value)
                        for key, value in (conversation.get("extension") or {}).items()
                        if value is not None
                    },
                    "ctx": {},
                },
                "createSingleChatConversationOption": {
                    "options": {
                        current_uid: {
                            "extension": {
                                key: str(value)
                                for key, value in (single.get("user_extension") or {}).items()
                                if value is not None
                            },
                            "hide": 0 if bool(single.get("visible", 1)) else 1,
                            "redPoint": self._to_int(single.get("redPoint")),
                            "mute": 1 if bool(single.get("muteNotification")) else 0,
                            "utags": {},
                        },
                    } if current_uid else {},
                    "ctags": {},
                    "msgReadStatusSetting": 1,
                },
                "receiverScope": {
                    "actualReceivers": [f"{r}@goofish" if "@" not in r else r for r in receivers],
                    "isShare": False,
                    "excludeReceivers": [],
                },
            }

            retryable_messages = {"system is error", "闲鱼走神了，您稍后再试～"}
            fallbacks = [full_send_options]
            if receivers:
                fallbacks.append({"actualReceivers": [f"{r}@goofish" if "@" not in r else r for r in receivers]})
            fallbacks.append({})

            response: Dict[str, Any] | None = None
            last_error: ValueError | None = None
            for index, option_payload in enumerate(fallbacks):
                response = await chat_client.send_rpc(
                    "/r/MessageSend/sendByReceiverScope",
                    [msg_payload, option_payload],
                )
                try:
                    self._ensure_chat_rpc_success(response, "发送闲鱼图片消息失败")
                    break
                except ValueError as exc:
                    last_error = exc
                    message = str(exc).strip()
                    is_last = index >= len(fallbacks) - 1
                    if is_last or message not in retryable_messages:
                        raise
            if response is None:
                if last_error:
                    raise last_error
                raise ValueError("发送闲鱼图片消息失败")
            return self._build_chat_send_result(cid=cid, summary="[图片]", payload=response)

    async def upload_and_send_chat_image(
        self,
        cid: str,
        filename: str,
        content: bytes,
        content_type: str = "image/png",
    ) -> XianyuChatSendResult:
        """上传图片并发送聊天消息，参照 XianYuApis 的 upload_media + send_image 流程"""
        upload_result = await self.upload_publish_image(filename, content, content_type)
        if not upload_result.image_url:
            raise ValueError("图片上传失败，未获取到图片 URL")
        return await self.send_chat_image(
            cid=cid,
            image_url=upload_result.image_url,
            width=upload_result.width,
            height=upload_result.height,
        )

    async def recall_chat_message(self, message_id: str) -> bool:
        """撤回闲鱼聊天消息，参照 XianYuApis 的 send_recall_message"""
        async with self._borrow_chat_ws_client() as chat_client:
            response = await chat_client.send_rpc("/r/MessageManager/recallMessage", [message_id])
            return response.get("code") == 200

    async def mark_chat_read(self, cid: str) -> bool:
        """标记闲鱼聊天消息已读，参照 XianYuApis 的 send_message_read"""
        async with self._borrow_chat_ws_client() as chat_client:
            response = await chat_client.send_rpc("/r/MessageStatus/read", [cid])
            return response.get("code") == 200

    async def create_chat_session(self, peer_user_id: str, item_id: str = "") -> dict[str, Any]:
        """创建单聊会话，参照 XianYuApis 的 create_chat"""
        try:
            async with self._borrow_chat_ws_client() as chat_client:
                myid = chat_client.profile.main_user_id or chat_client.profile.user_id
                body = [
                    {
                        "pairFirst": f"{peer_user_id}@goofish",
                        "pairSecond": f"{myid}@goofish",
                        "bizType": "1",
                        "extension": {"itemId": item_id} if item_id else {},
                        "ctx": {"appVersion": "1.0", "platform": "web"},
                    }
                ]
                response = await chat_client.send_rpc("/r/SingleChatConversation/create", body)
                self._ensure_chat_rpc_success(response, "创建闲鱼聊天会话失败")
                result_body = response.get("body") or {}
                cid = str(result_body.get("cid") or "")
                return {"success": True, "cid": cid}
        except ValueError as exc:
            return {"success": False, "message": str(exc)}

    def decode_chat_push(self, push_payload: Dict[str, Any]) -> Dict[str, Any]:
        """解码闲鱼聊天推送消息，参照 XianYuApis 的 handler.py"""
        lwp = push_payload.get("lwp", "")
        body = push_payload.get("body") or {}

        if lwp in ("/s/sync", "/s/sync_failover"):
            return self._decode_sync_push(body)
        if lwp == "/s/para":
            return {"type": "typing", "data": body}
        if lwp == "/push/kickout":
            return {"type": "kickout", "data": body}
        if lwp == "/s/vulcan":
            return {"type": "vulcan", "data": body}
        if lwp == "/s/session/remove":
            return {"type": "session_remove", "data": body}

        return {"type": "other", "lwp": lwp, "data": body}

    def _decode_sync_push(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """解码同步推送，参照 XianYuApis 的 handle_sync_push"""
        if not isinstance(body, dict) or "syncPushPackage" not in body:
            return {"type": "sync", "items": []}

        sync_package = body.get("syncPushPackage", {})
        data_list = sync_package.get("data", [])
        items = []
        for item in data_list:
            biz_type = item.get("bizType", 0)
            inner_data = str(item.get("data") or "").strip()
            decoded = self._decode_message_data(inner_data) if inner_data else {}
            items.append({
                "biz_type": biz_type,
                "biz_label": self._BIZ_TYPE_NAMES.get(biz_type, f"bizType={biz_type}"),
                "decoded": decoded,
            })
        return {"type": "sync", "items": items}

    _BIZ_TYPE_NAMES = {
        40000: "新消息", 40001: "会话可见性变更", 40002: "会话免打扰变更",
        40003: "会话置顶变更", 40004: "清除红点", 40005: "会话扩展变更",
        40006: "输入状态", 40007: "群聊用户扩展更新", 40010: "会话UserTags更新",
        40101: "消息删除", 40102: "已读回执", 40103: "已读回执(发送方)",
        40104: "消息撤回", 40105: "消息扩展变更", 40106: "会话清空",
        40108: "消息用户扩展变更", 40200: "群聊创建", 40201: "加入群聊",
        40202: "他人加入群聊", 40203: "被踢出群聊", 40204: "他人被踢出群聊",
        40205: "退出群聊", 40206: "他人退出群聊", 40207: "群聊解散",
        40208: "群名更新", 40209: "群图标更新", 40210: "会话修正",
        40211: "全员禁言", 40212: "禁言黑名单变更", 40213: "禁言白名单变更",
        40214: "群管理员变更", 40215: "群主变更", 40217: "群扩展变更",
        40221: "群成员昵称变更",
    }

    def _encode_chat_text(self, text: str) -> str:
        """编码文本消息为 base64，参照 XianYuApis 的 encode_text"""
        text_data = {"contentType": 1, "text": {"text": text}}
        return base64.b64encode(
            json.dumps(text_data, separators=(",", ":"), ensure_ascii=False).encode()
        ).decode()

    def _encode_chat_image(self, url: str, width: int = 0, height: int = 0) -> str:
        """编码图片消息为 base64，参照 XianYuApis 的 encode_image"""
        image_data = {
            "contentType": 2,
            "image": {"pics": [{"type": 0, "url": url, "width": width, "height": height}]},
        }
        return base64.b64encode(
            json.dumps(image_data, separators=(",", ":"), ensure_ascii=False).encode()
        ).decode()

    async def _request_chat_ai_reply(
        self,
        *,
        messages: list[dict[str, str]],
        provider: XianyuChatAiProvider | None = None,
        config: XianyuChatAiConfig | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> str:
        if provider is None and config is None:
            raise ValueError("AI 供应商未配置")

        # 测试场景：使用临时 api_key（不持久化）
        if self._temp_provider_api_key:
            api_key = self._temp_provider_api_key
        elif provider is not None:
            api_key = self.chat_ai_store.load_secret_api_key(provider.id).strip()
        else:
            api_key = self._load_secret_chat_ai_api_key()
        if not api_key:
            raise ValueError("AI API Key 未配置")

        base_url = (provider.base_url if provider is not None else config.base_url).rstrip("/")
        model_name = provider.model if provider is not None else config.model
        payload = {
            "model": model_name,
            "messages": messages,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        }
        body = json.dumps(payload, ensure_ascii=provider is not None).encode("utf-8")

        async with httpx.AsyncClient(timeout=30.0, transport=transport) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                content=body,
            )
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        if not choices:
            raise ValueError("AI 接口未返回可用回复")

        message = choices[0].get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            finish_reason = str(choices[0].get("finish_reason") or choices[0].get("native_finish_reason") or "")
            usage = data.get("usage") or {}
            details = usage.get("completion_tokens_details") or {}
            completion_tokens = self._to_int(usage.get("completion_tokens"))
            reasoning_tokens = self._to_int(details.get("reasoning_tokens"))
            answer_tokens = max(completion_tokens - reasoning_tokens, 0) if completion_tokens else 0
            usage_text = json.dumps(usage, ensure_ascii=False, separators=(",", ":")) if usage else "{}"
            if reasoning_tokens and answer_tokens:
                raise ValueError(
                    "AI 接口返回了空回复；推测是网关将推理模型转换为 chat.completion 时丢失 content。"
                    f"finish_reason={finish_reason or 'unknown'}，answer_tokens={answer_tokens}，usage={usage_text}。"
                    "建议切换为非推理模型（如 gpt-4o、gpt-4.1-mini）或更换 OpenAI 兼容网关。"
                )
            raise ValueError(
                f"AI 接口返回了空回复；finish_reason={finish_reason or 'unknown'}，usage={usage_text}"
            )
        return content

    def _extract_ai_candidate(self, item: dict[str, Any]) -> dict[str, str] | None:
        decoded = item.get("decoded") or {}
        try:
            biz_type = int(str(item.get("biz_type") or 0))
        except (TypeError, ValueError):
            biz_type = 0
        if biz_type not in (40, 40000):
            return None

        raw_text = str(decoded.get("raw_text") or "")

        def normalize_cid(value: Any) -> str:
            text = str(value or "").strip()
            if not text:
                return ""
            # protobuf 解密文本里有时带 ".PNM" 后缀；RPC 需要纯 cid。
            text = text.split(".PNM", 1)[0]
            if "@" in text:
                head, domain = text.split("@", 1)
                return f"{head}@{domain.split()[0]}" if head else ""
            return text

        def build_candidate(cid: Any, sender_uid: Any, text: Any, sender_name: Any = "") -> dict[str, str] | None:
            normalized_cid = normalize_cid(cid)
            normalized_sender = str(sender_uid or "").strip().split("@", 1)[0]
            normalized_text = str(text or "").strip()
            if not normalized_cid or not normalized_sender or not normalized_text:
                return None
            message_id = str(decoded.get("message_id") or "").strip()
            key_material = "|".join(
                part
                for part in (
                    normalized_cid,
                    normalized_sender,
                    normalized_text,
                    message_id,
                    raw_text,
                )
                if part
            )
            if not key_material:
                key_material = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
            key = hashlib.sha1(key_material.encode("utf-8", errors="ignore")).hexdigest()
            return {
                "cid": normalized_cid,
                "sender_uid": normalized_sender,
                "sender_name": str(sender_name or "").strip(),
                "text": normalized_text,
                "message_key": key,
            }

        def extract_cid_from_text(text: str) -> str:
            if not text:
                return ""
            patterns = (
                r"(?:\"|')?(?:cid|sid|sessionId)(?:\"|')?\s*[:=]\s*(?:\"|')?([0-9A-Za-z._-]+(?:@goofish)?)",
                r"(?:sid|sessionId)=([0-9A-Za-z._-]+)",
                r"([0-9]{6,}@goofish)",
            )
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    return normalize_cid(match.group(1))
            return ""

        def recursive_find_cid(obj: Any) -> str:
            if isinstance(obj, dict):
                for key in ("cid", "sid", "sessionId"):
                    value = obj.get(key)
                    if value:
                        cid = normalize_cid(value)
                        if cid:
                            return cid
                for value in obj.values():
                    cid = recursive_find_cid(value)
                    if cid:
                        return cid
            elif isinstance(obj, list):
                for value in obj:
                    cid = recursive_find_cid(value)
                    if cid:
                        return cid
            return ""

        for obj in decoded.get("json_objects") or []:
            payload = obj.get("1") or {}
            meta = payload.get("10") or {}
            cid = str(payload.get("2") or "").strip()
            sender_uid = str(meta.get("senderUserId") or "").strip()
            text = str(meta.get("reminderContent") or "").strip()
            sender_name = str(meta.get("reminderTitle") or "").strip()
            candidate = build_candidate(cid, sender_uid, text, sender_name)
            if candidate:
                return candidate

        # 解密 fallback：有些推送无法完整提取到 json_objects[0]["1"]["10"]，
        # 但 _decode_message_data 已经从全文递归提取到了顶层 sender/reminder 字段。
        fallback_cid = str(decoded.get("cid") or "").strip()
        if not fallback_cid:
            for obj in decoded.get("json_objects") or []:
                fallback_cid = recursive_find_cid(obj)
                if fallback_cid:
                    break
        if not fallback_cid:
            for url in decoded.get("urls") or []:
                fallback_cid = extract_cid_from_text(str(url))
                if fallback_cid:
                    break
        if not fallback_cid:
            fallback_cid = extract_cid_from_text(raw_text)

        return build_candidate(
            fallback_cid,
            decoded.get("sender_user_id"),
            decoded.get("reminder_content"),
            decoded.get("nickname"),
        )

    def _remember_ai_message_key(self, key: str) -> bool:
        if key in self._processed_ai_message_set:
            return False
        if len(self._processed_ai_message_keys) == self._processed_ai_message_keys.maxlen:
            dropped = self._processed_ai_message_keys.popleft()
            self._processed_ai_message_set.discard(dropped)
        self._processed_ai_message_keys.append(key)
        self._processed_ai_message_set.add(key)
        return True

    def _build_chat_ai_messages(
        self,
        *,
        provider: XianyuChatAiProvider,
        text: str,
        cid: str = "",
        sender_name: str = "",
        item_title: str = "",
        history: list[XianyuChatMessage] | None = None,
    ) -> list[dict[str, str]]:
        system_prompt = provider.system_prompt or "你是闲鱼客服助手，回复要简洁、礼貌、像真人卖家。"
        context_parts: list[str] = []
        if cid:
            context_parts.append(f"会话 CID：{cid}")
        if sender_name:
            context_parts.append(f"当前买家昵称：{sender_name}")
        if item_title:
            context_parts.append(f"当前咨询商品：{item_title}")
        if context_parts:
            system_prompt = system_prompt.rstrip() + "\n\n" + "\n".join(context_parts)

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for item in history or []:
            content = str(item.text or item.summary or "").strip()
            if not content:
                continue
            messages.append({
                "role": "assistant" if item.direction == "out" else "user",
                "content": content,
            })
        messages.append({"role": "user", "content": text})
        return messages

    async def _get_conversation_item_title(self, cid: str) -> str:
        try:
            page = await self.list_chat_conversations(offset=0, limit=40)
        except Exception:
            return ""
        cid_variants = set(self._chat_cid_variants(cid))
        for session in page.conversations:
            if session.cid in cid_variants or session.session_id in cid_variants:
                return session.item_title or session.title or ""
        return ""

    def _chat_cid_variants(self, cid: str) -> list[str]:
        """返回同一聊天会话的完整/短 CID 兼容写法。

        历史配置里会话 AI 开关曾经用短 cid（如 ``123``）保存；新聊天接口和
        前端会话列表更多使用完整 cid（如 ``123@goofish``）。自动回复链路需要
        同时兼容两种状态，否则会出现“当前会话已开启 AI 但后台判断未开启”。
        """
        text = str(cid or "").strip()
        if not text:
            return []
        short = text.split("@", 1)[0]
        full = text if "@" in text else f"{short}@{self.chat_domain}"
        return list(dict.fromkeys([text, full, short]))

    async def maybe_auto_reply_from_decoded_push(self, profile: XianyuChatProfile, decoded: dict[str, Any]) -> str | None:
        if decoded.get("type") != "sync":
            return None

        config = self.get_chat_ai_config()
        if not config.enabled:
            logger.debug("AI auto-reply skipped: 总开关未启用")
            return None

        provider = self.chat_ai_store.get_active_provider()
        if not provider:
            logger.debug("AI auto-reply skipped: 没有激活的 AI 供应商")
            return None

        current_user_id = profile.main_user_id or profile.user_id
        items = decoded.get("items") or []
        if not items:
            return None

        for idx, item in enumerate(items):
            biz_type = item.get("biz_type")
            candidate = self._extract_ai_candidate(item)
            if not candidate:
                if biz_type == 40000:
                    logger.debug(f"AI auto-reply skipped[{idx}]: biz_type=40000 但解析失败")
                continue
            if candidate["sender_uid"] == current_user_id:
                logger.debug(f"AI auto-reply skipped[{idx}]: 消息是自己发的")
                continue
            cid_variants = self._chat_cid_variants(candidate["cid"])
            enabled_cid = next(
                (cid for cid in cid_variants if self.chat_ai_store.get_session_enabled(cid)),
                "",
            )
            reply_cid = enabled_cid or candidate["cid"]
            session_on = bool(enabled_cid)
            logger.info(
                f"AI 候选消息 cid={candidate['cid']} sender={candidate['sender_uid']} "
                f"text={candidate['text'][:40]!r} session_ai_on={session_on}"
            )
            if not session_on:
                self._log.info("AI 自动回复跳过：当前会话未开启 cid=%s", candidate["cid"])
                logger.debug(f"AI auto-reply skipped: 会话 {candidate['cid']} 未启用 AI")
                continue
            if not self._remember_ai_message_key(candidate["message_key"]):
                logger.debug(f"AI auto-reply skipped: 消息已处理过 key={candidate['message_key']}")
                continue

            try:
                await self._mark_chat_read_before_ai_reply(reply_cid=reply_cid, source_cid=candidate["cid"])
                item_title = await self._get_conversation_item_title(reply_cid)
                history: list[XianyuChatMessage] = []
                try:
                    page = await self.list_chat_messages(reply_cid, limit=8)
                    history = [
                        item
                        for item in page.messages
                        if (item.text or item.summary)
                        and str(item.text or item.summary or "").strip() != candidate["text"]
                    ][-6:]
                except Exception:
                    history = []
                messages = self._build_chat_ai_messages(
                    provider=provider,
                    text=candidate["text"],
                    cid=reply_cid,
                    sender_name=candidate.get("sender_name", ""),
                    item_title=item_title,
                    history=history,
                )
                logger.info(f"AI 调用供应商 {provider.name} model={provider.model}")
                reply = await self._request_chat_ai_reply(provider=provider, messages=messages)
                logger.info(f"AI 回复 cid={reply_cid} reply={reply[:80]!r}")
                await self.send_chat_text(cid=reply_cid, text=reply)
                logger.info(f"AI 自动回复已发送 cid={reply_cid}")
                return reply
            except Exception as exc:
                logger.error(f"AI 自动回复失败 cid={reply_cid}: {exc}")
                raise

        return None

    async def _mark_chat_read_before_ai_reply(self, reply_cid: str, source_cid: str = "") -> bool:
        """AI 自动回复前先把会话标记为已读。

        参考 XianYuApis 的监听处理顺序：收到私信推送后先确认会话已读，再执行业务回复。
        已读失败不应阻断自动回复；不同入口保存的 cid 可能是完整 cid 或短 cid，所以这里按
        完整/原始/短 cid 依次轻量尝试。
        """
        candidates: list[str] = []
        for cid in (reply_cid, source_cid):
            variants = self._chat_cid_variants(cid)
            if not variants:
                continue
            # 网页端通常使用完整 cid；无论传入的是短 cid 还是完整 cid，都优先尝试带 @ 的版本。
            preferred = [variant for variant in variants if "@" in variant]
            preferred.extend(variants)
            for candidate in preferred:
                candidate = str(candidate or "").strip()
                if candidate and candidate not in candidates:
                    candidates.append(candidate)

        last_error = ""
        for cid in candidates:
            try:
                if await self.mark_chat_read(cid):
                    logger.info("AI 自动回复前已标记会话已读 cid=%s", cid)
                    return True
            except Exception as exc:
                last_error = str(exc)
                logger.debug("AI 自动回复前标记已读失败 cid=%s: %s", cid, exc)

        if candidates:
            logger.warning("AI 自动回复前标记已读未成功 cid=%s error=%s", candidates[0], last_error or "unknown")
        return False

    def _update_decoded_message_fields(self, result: Dict[str, Any], obj: Any) -> None:
        """从解码后的 JSON 片段中递归提取 AI 自动回复需要的字段。"""
        if isinstance(obj, dict):
            field_map = {
                "senderUserId": "sender_user_id",
                "reminderContent": "reminder_content",
                "reminderTitle": "nickname",
                "messageId": "message_id",
                "cid": "cid",
                "sid": "cid",
                "sessionId": "cid",
            }
            for source_key, result_key in field_map.items():
                value = obj.get(source_key)
                if value is not None and not result.get(result_key):
                    result[result_key] = str(value)
            for value in obj.values():
                self._update_decoded_message_fields(result, value)
        elif isinstance(obj, list):
            for value in obj:
                self._update_decoded_message_fields(result, value)

    def _build_decoded_message_result(self, text: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "raw_text": text,
            "json_objects": [],
            "user_ids": re.findall(r"(\d+)@goofish", text),
            "urls": [],
            "nickname": "",
            "reminder_content": "",
            "sender_user_id": "",
            "cid": "",
            "message_id": "",
        }

        seen_snippets: set[str] = set()

        def add_json_object(obj: Any, snippet: str = "") -> None:
            if isinstance(obj, dict):
                key = snippet or json.dumps(obj, ensure_ascii=False, sort_keys=True)
                if key not in seen_snippets:
                    seen_snippets.add(key)
                    result["json_objects"].append(obj)
                self._update_decoded_message_fields(result, obj)
            elif isinstance(obj, list):
                self._update_decoded_message_fields(result, obj)
                for entry in obj:
                    add_json_object(entry)

        stripped = text.strip()
        if stripped.startswith(("{", "[")):
            with contextlib.suppress(Exception):
                add_json_object(json.loads(stripped), stripped)

        brace_count = 0
        start = -1
        for i, char in enumerate(text):
            if char == "{":
                if brace_count == 0:
                    start = i
                brace_count += 1
            elif char == "}" and brace_count > 0:
                brace_count -= 1
                if brace_count == 0 and start >= 0:
                    snippet = text[start : i + 1]
                    try:
                        add_json_object(json.loads(snippet), snippet)
                    except Exception:
                        pass
                    start = -1

        url_match = re.search(r"(fleamarket://[^\s\x00]+?)(?=\s|senderUserId|$)", text)
        if url_match:
            result["urls"].append(url_match.group(1))
        return result

    def _decode_message_data(self, encoded: str) -> Dict[str, Any]:
        """解码推送消息的 data 字段，参照 XianYuApis 的 decode_message_data"""
        raw = str(encoded or "")
        if raw.lstrip().startswith(("{", "[")):
            return self._build_decoded_message_result(raw)

        try:
            padding = "=" * (-len(raw) % 4)
            decoded = base64.b64decode(raw + padding)
            text = decoded.decode("utf-8", errors="replace")
        except Exception:
            text = raw

        result = self._build_decoded_message_result(text)
        if result.get("sender_user_id") or result.get("reminder_content"):
            return result

        with contextlib.suppress(Exception):
            decrypted = xianyu_decrypt(raw)
            if decrypted:
                decrypted_result = self._build_decoded_message_result(str(decrypted))
                if (
                    decrypted_result.get("json_objects")
                    or decrypted_result.get("sender_user_id")
                    or decrypted_result.get("reminder_content")
                ):
                    return decrypted_result
        return result

    async def open_chat_session(self, item_id: str, peer_user_id: str) -> dict[str, Any]:
        """在项目内打开指定卖家的聊天会话"""
        normalized_item_id = str(item_id or "").strip()
        normalized_peer_user_id = str(peer_user_id or "").strip()

        if not normalized_item_id or not normalized_peer_user_id:
            return {"success": False, "message": "商品或卖家信息不完整"}

        page = await self.list_chat_conversations(offset=0, limit=40)
        exact = next(
            (
                session
                for session in page.conversations
                if session.peer_user_id == normalized_peer_user_id and session.item_id == normalized_item_id
            ),
            None,
        )
        fallback = next(
            (
                session
                for session in page.conversations
                if session.peer_user_id == normalized_peer_user_id
            ),
            None,
        )
        target = exact or fallback
        if target:
            return {
                "success": True,
                "message": "已打开会话",
                "cid": target.cid,
                "session": target,
            }

        return await self._open_chat_session_via_bootstrap(
            item_id=normalized_item_id,
            peer_user_id=normalized_peer_user_id,
        )

    async def _open_chat_session_via_bootstrap(self, item_id: str, peer_user_id: str) -> dict[str, Any]:
        """最小化刷新聊天上下文，尝试发现已存在的目标会话，不主动发消息。"""
        async with self._borrow_chat_ws_client() as chat_client:
            response = await chat_client.send_rpc("/r/Conversation/listNewest", [0, 40])
            self._ensure_chat_rpc_success(response, "获取闲鱼聊天会话失败")
            conversations = [
                self._map_chat_conversation(item, chat_client.profile)
                for item in response.get("body") or []
                if isinstance(item, dict)
            ]
            exact = next(
                (
                    session
                    for session in conversations
                    if session.peer_user_id == peer_user_id and session.item_id == item_id
                ),
                None,
            )
            fallback = next(
                (
                    session
                    for session in conversations
                    if session.peer_user_id == peer_user_id
                ),
                None,
            )
            target = exact or fallback
            if target:
                return {
                    "success": True,
                    "message": "已打开会话",
                    "cid": target.cid,
                    "session": target,
                }
            create_result = await self.create_chat_session(
                peer_user_id=peer_user_id,
                item_id=item_id,
            )
            if create_result.get("success"):
                return {
                    "success": True,
                    "message": "已创建会话",
                    "cid": create_result["cid"],
                }
            return {
                "success": False,
                "message": create_result.get("message", "创建会话失败"),
            }

    def _is_chat_auth_error(self, message: str) -> bool:
        return any(
            marker in message
            for marker in (
                "token is not found",
                "FAIL_SYS_USER_VALIDATE",
                "FAIL_SYS_SESSION_EXPIRED",
                "闲鱼聊天鉴权失败",
                "闲鱼登录已过期",
                "Cookie",
            )
        )

    async def _create_connected_chat_ws_client(self) -> XianyuChatWsClient:
        """创建一条新的闲鱼聊天 WebSocket 连接。调用方负责决定是否缓存复用。"""
        cookie = self._require_xianyu_cookie()
        async with self._create_http_client(cookie) as client:
            # 这里不预先额外调用 loginuser.get；_build_chat_bootstrap 会按需获取
            # profile + login.token。减少建连时连续 HTTP 请求，降低 fresh cookie
            # 被风控的概率。
            bootstrap = await self._build_chat_bootstrap(client, include_token=True)
            runtime_cookie = self._build_cookie_header(client) or cookie

        chat_client = XianyuChatWsClient(
            ws_url=self.chat_ws_url,
            app_key=self.chat_ws_app_key,
            access_token=bootstrap["access_token"],
            device_id=bootstrap["device_id"],
            user_agent=self.default_headers["user-agent"],
            sdk_user_agent=self._build_chat_sdk_user_agent(),
            profile=bootstrap["profile"],
        )
        try:
            await chat_client.connect(cookie=runtime_cookie)
        except ValueError as exc:
            with contextlib.suppress(Exception):
                await chat_client.close()
            message = str(exc).strip()
            if message in {"token is not found", "FAIL_SYS_USER_VALIDATE", "FAIL_SYS_SESSION_EXPIRED"}:
                raise ValueError(
                    self._format_chat_auth_failure(
                        reason=message,
                        bootstrap=bootstrap,
                        cookie=runtime_cookie,
                    )
                ) from exc
            raise
        except Exception:
            with contextlib.suppress(Exception):
                await chat_client.close()
            raise
        return chat_client

    async def open_chat_ws_client(self) -> XianyuChatWsClient:
        """获取共享闲鱼聊天 WebSocket 客户端。

        聊天页、消息列表、发送消息、后台 AI 监听共用同一条连接，避免多条 WS 反复调用
        login.token 触发风控，也避免前端 WS 关闭时把后台 AI 监听链路切断。
        """
        async with self._shared_chat_client_lock:
            shared = self._shared_chat_client
            if shared is not None and shared.is_connected():
                return shared

            if shared is not None:
                self._shared_chat_client = None
                with contextlib.suppress(Exception):
                    await shared.close()

            try:
                chat_client = await self._create_connected_chat_ws_client()
            except ValueError as exc:
                message = str(exc).strip()
                if not self._is_chat_auth_error(message):
                    raise
                # 不在鉴权/风控错误后立刻二次请求 login.token。会话切换时最容易
                # 因连续握手被判风险；这里交给后台保活刷新 loginuser.get 后再重连。
                with contextlib.suppress(Exception):
                    await self._refresh_chat_runtime_token()
                raise

            self._shared_chat_client = chat_client
            return chat_client

    @contextlib.asynccontextmanager
    async def _borrow_chat_ws_client(self):
        """借用共享 ws；如果后台 listener 已经维护着共享 ws，就直接复用，避免每次 HTTP 请求都重新握手触发风控。

        没有共享 ws 时会创建并缓存一条共享连接，不在单个 HTTP 请求结束时关闭。
        """
        chat_client = await self.open_chat_ws_client()
        yield chat_client

    async def _execute_api(
        self,
        client: httpx.AsyncClient,
        api_name: str,
        api_url: str,
        payload: Dict,
        extra_params: Optional[Dict[str, str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict:
        """执行通用闲鱼接口请求，参照 xianyu-cli 的 Cookie 冻结 + index API 刷新策略"""
        response_data = await self._perform_api_request(
            client,
            api_name=api_name,
            api_url=api_url,
            payload=payload,
            extra_params=extra_params,
            extra_headers=extra_headers,
        )

        if self._is_token_expired(response_data):
            self._log.warning("API %s token 过期，直接重试", api_name)
            response_data = await self._perform_api_request(
                client,
                api_name=api_name,
                api_url=api_url,
                payload=payload,
                extra_params=extra_params,
                extra_headers=extra_headers,
                allow_bootstrap=False,
            )

        if self._is_success(response_data):
            self._sync_runtime_cookie(client)
            return response_data

        message = self._extract_error(response_data)
        if "FAIL_SYS_USER_VALIDATE" in message or "FAIL_SYS_SESSION_EXPIRED" in message:
            self._log.warning("API %s 鉴权失败(%s)，直接重试", api_name, message)
            retry_data = await self._perform_api_request(
                client,
                api_name=api_name,
                api_url=api_url,
                payload=payload,
                extra_params=extra_params,
                allow_bootstrap=False,
            )
            if self._is_success(retry_data):
                self._sync_runtime_cookie(client)
                return retry_data

            retry_msg = self._extract_error(retry_data)
            if "FAIL_SYS_TOKEN_EXOIRED" in retry_msg:
                self._log.warning("API %s 重试后 token 过期，再次重试", api_name)
                retry_data = await self._perform_api_request(
                    client,
                    api_name=api_name,
                    api_url=api_url,
                    payload=payload,
                    extra_params=extra_params,
                    allow_bootstrap=False,
                )
                if self._is_success(retry_data):
                    self._sync_runtime_cookie(client)
                    return retry_data

            retry_msg = self._extract_error(retry_data)
            self._log.error("API %s 重试失败: %s", api_name, retry_msg)
            if "RGV587_ERROR" in retry_msg:
                captcha_url = ""
                if isinstance(retry_data, dict):
                    captcha_url = retry_data.get("data", {}).get("url", "")
                if not captcha_url and isinstance(response_data, dict):
                    captcha_url = response_data.get("data", {}).get("url", "")
                if captcha_url:
                    raise ValueError(
                        f"闲鱼接口被风控拦截，请在浏览器中打开以下链接完成验证后重新更新 Cookie：{captcha_url}"
                    )
                raise ValueError("闲鱼接口被风控拦截，请尝试在浏览器中访问闲鱼网站完成验证后重新更新 Cookie")
            if "FAIL_SYS_USER_VALIDATE" in retry_msg or "FAIL_SYS_SESSION_EXPIRED" in retry_msg:
                raise ValueError("闲鱼登录已过期，请重新登录闲鱼后更新 Cookie")
            raise ValueError(retry_msg)
        raise ValueError(message)

    async def _perform_api_request(
        self,
        client: httpx.AsyncClient,
        api_name: str,
        api_url: str,
        payload: Dict,
        extra_params: Optional[Dict[str, str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        allow_bootstrap: bool = True,
    ) -> Dict:
        """发起闲鱼 API 请求，参照 xianyu-cli 通过 Cookie header 发送冻结 Cookie，不更新 jar"""
        if not self._get_cookie_value(client, "_m_h5_tk") and allow_bootstrap:
            await self._bootstrap_token(
                client,
                api_name=api_name,
                api_url=api_url,
                payload=payload,
            )

        data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        timestamp = str(int(time.time()) * 1000)
        token = self._get_sign_token(client)
        sign = self._build_sign(token, timestamp, data_json)
        self._log.debug("API %s sign token=%s... ts=%s", api_name, token[:8] if token else "NONE", timestamp)

        params = {
            "jsv": "2.7.2",
            "appKey": self.app_key,
            "t": timestamp,
            "sign": sign,
            "v": "1.0",
            "type": "originaljson",
            "accountSite": "xianyu",
            "dataType": "json",
            "timeout": "20000",
            "api": api_name,
            "sessionOption": "AutoLoginOnly",
            "spm_cnt": "a21ybx.im.0.0",
        }
        if extra_params:
            params.update(extra_params)

        await asyncio.sleep(random.uniform(0.1, 0.3))

        response = await client.post(
            api_url,
            params=params,
            data={"data": data_json},
            headers=extra_headers or None,
        )
        response.raise_for_status()
        self._extract_token_cookies(client, response)
        return response.json()

    async def _warmup_token(self, client: httpx.AsyncClient) -> None:
        """使用轻量 timestamp 接口预热 _m_h5_tk"""
        if self._get_cookie_value(client, "_m_h5_tk"):
            return

        try:
            response = await client.get(self.timestamp_api_url)
            response.raise_for_status()
            self._extract_token_cookies(client, response)
        except Exception:
            pass

    async def _refresh_login_state(self, client: httpx.AsyncClient) -> None:
        """刷新登录态，参照 XianYuApis 的 refresh_token 使用 loginuser.get API"""
        try:
            data_json = "{}"
            timestamp = str(int(time.time()) * 1000)
            token = self._get_sign_token(client)
            sign = self._build_sign(token, timestamp, data_json)

            params = {
                "jsv": "2.7.2",
                "appKey": self.app_key,
                "t": timestamp,
                "sign": sign,
                "v": "1.0",
                "type": "originaljson",
                "accountSite": "xianyu",
                "dataType": "json",
                "timeout": "20000",
                "api": self.refresh_token_api_name,
                "sessionOption": "AutoLoginOnly",
                "spm_cnt": "a21ybx.im.0.0",
                "spm_pre": "a21ybx.item.want.1.12523da6waCtUp",
                "log_id": "12523da6waCtUp",
            }

            response = await client.post(
                self.refresh_token_api_url,
                params=params,
                data={"data": data_json},
            )
            response.raise_for_status()
            self._extract_token_cookies(client, response)
            self._sync_runtime_cookie(client)
        except Exception:
            pass

    async def _bootstrap_token(
        self,
        client: httpx.AsyncClient,
        api_name: str,
        api_url: str,
        payload: Dict,
    ) -> None:
        """在没有 token 时先引导服务端下发新的 `_m_h5_tk`"""
        data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        timestamp = str(int(time.time()) * 1000)

        response = await client.post(
            api_url,
            params={
                "jsv": "2.7.2",
                "appKey": self.app_key,
                "t": timestamp,
                "sign": "",
                "v": "1.0",
                "type": "originaljson",
                "accountSite": "xianyu",
                "dataType": "json",
                "timeout": "20000",
                "api": api_name,
                "sessionOption": "AutoLoginOnly",
                "spm_cnt": "a21ybx.im.0.0",
            },
            data={"data": data_json},
        )
        response.raise_for_status()
        self._extract_token_cookies(client, response)

    def _build_payload(self, request: XianyuSearchRequest) -> Dict:
        """构建闲鱼搜索 payload"""
        division_list = []
        if request.province and request.city:
            division_list.append({"province": request.province, "city": request.city})

        extra_filter_value = {
            "divisionList": division_list,
            "excludeMultiPlacesSellers": "0",
            "extraDivision": "",
        }

        return {
            "pageNumber": request.page,
            "keyword": request.keyword,
            "fromFilter": bool(request.prop_values),
            "rowsPerPage": request.page_size,
            "sortValue": request.sort_value,
            "sortField": request.sort_field,
            "customDistance": "",
            "gps": "",
            "propValueStr": request.prop_values,
            "customGps": "",
            "searchReqFromPage": "pcSearch",
            "extraFilterValue": json.dumps(extra_filter_value, ensure_ascii=False, separators=(",", ":")),
            "userPositionJson": "{}",
        }

    def _map_result(self, payload: Dict, request: XianyuSearchRequest) -> XianyuSearchResult:
        """映射接口返回为前端稳定数据结构"""
        result_info = payload.get("data", {}).get("resultInfo", {})
        search_control = result_info.get("searchResControlFields", {})
        filters = self._extract_filters(result_info)
        items = self._extract_items(payload.get("data", {}).get("resultList", []))
        location = search_control.get("choosePosition") or request.city or request.province

        return XianyuSearchResult(
            keyword=request.keyword,
            total=int(search_control.get("numFound") or 0),
            page=request.page,
            page_size=request.page_size,
            has_more=bool(search_control.get("nextPage")),
            location=location,
            search_id=str(search_control.get("searchId") or ""),
            items=items,
            filters=filters,
        )

    def _map_user_profile(self, payload: Dict) -> XianyuUserProfile:
        """映射闲鱼登录用户信息"""
        base_info = payload.get("data", {}).get("module", {}).get("base", {})
        display_name = str(base_info.get("displayName") or "")
        if not display_name:
            raise ValueError("未获取到闲鱼登录用户信息，请检查 Cookie 是否有效")

        return XianyuUserProfile(
            display_name=display_name,
            avatar=self._normalize_image_url(str(base_info.get("avatar") or "")),
            sold_count=self._to_int(base_info.get("soldCount")),
            purchase_count=self._to_int(base_info.get("purchaseCount")),
            followers=self._to_int(base_info.get("followers")),
            following=self._to_int(base_info.get("following")),
            collection_count=self._to_int(base_info.get("collectionCount")),
        )

    def _map_item_detail(self, payload: Dict, item_id: str) -> XianyuItemDetail:
        """映射闲鱼宝贝详情"""
        raw = payload.get("data", {})
        data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        item_do = data.get("itemDO") or data.get("item") or {}
        seller_do = data.get("sellerDO") or data.get("seller") or {}

        title = str(item_do.get("title") or "")
        if not title:
            raise ValueError("未获取到宝贝详情，请稍后重试")

        image_list = item_do.get("imageInfos") or item_do.get("pics") or []
        images: List[str] = []
        for image in image_list:
            if isinstance(image, dict):
                url = str(image.get("url") or image.get("picUrl") or "")
            else:
                url = str(image or "")
            if url:
                images.append(self._normalize_image_url(url))

        tags = self._dedupe_texts(
            [str(tag.get("text") or "") for tag in item_do.get("commonTags", [])]
            + [str(tag.get("text") or "") for tag in item_do.get("itemLabelExtList", [])]
            + [str(tag or "") for tag in item_do.get("tags", [])]
        )

        attributes: List[XianyuDetailAttribute] = []
        for attribute in item_do.get("cpvLabels", []) or item_do.get("attributes", []) or []:
            if not isinstance(attribute, dict):
                continue
            name = str(attribute.get("propertyName") or attribute.get("name") or "")
            value = str(attribute.get("valueName") or attribute.get("value") or "")
            if name and value:
                attributes.append(XianyuDetailAttribute(name=name, value=value))

        publish_time = str(item_do.get("GMT_CREATE_DATE_KEY") or "")
        if not publish_time:
            publish_time = self._format_datetime(item_do.get("gmtCreate"))

        seller_name = str(seller_do.get("nick") or seller_do.get("uniqueName") or "")

        return XianyuItemDetail(
            item_id=str(item_do.get("itemId") or item_id),
            title=title,
            price=self._format_detail_price(item_do.get("soldPrice") or item_do.get("price")),
            original_price=self._format_detail_price(item_do.get("originalPrice")),
            desc=str(item_do.get("desc") or ""),
            images=images,
            location=str(
                item_do.get("location")
                or item_do.get("province")
                or item_do.get("city")
                or seller_do.get("publishCity")
                or seller_do.get("city")
                or ""
            ),
            publish_time=publish_time,
            status=str(item_do.get("itemStatusStr") or item_do.get("status") or ""),
            transport_fee=self._format_transport_fee(item_do.get("transportFee")),
            browse_count=self._to_int(item_do.get("browseCnt")),
            want_count=self._to_int(item_do.get("wantCnt")),
            collect_count=self._to_int(item_do.get("collectCnt")),
            tags=tags,
            attributes=attributes,
            seller_name=seller_name,
            seller_user_id=str(seller_do.get("userId") or seller_do.get("sellerId") or ""),
            seller_avatar=self._normalize_image_url(
                str(seller_do.get("portraitUrl") or seller_do.get("avatar") or "")
            ),
            seller_summary=str(seller_do.get("xianyuSummary") or seller_do.get("summary") or ""),
            seller_city=str(seller_do.get("city") or seller_do.get("publishCity") or ""),
            seller_last_visit=str(seller_do.get("lastVisitTime") or ""),
            seller_item_count=self._to_int(seller_do.get("itemCount")),
            detail_url=f"https://www.goofish.com/item?id={item_id}",
        )

    async def _build_chat_bootstrap(
        self,
        client: httpx.AsyncClient,
        include_token: bool = True,
    ) -> Dict[str, Any]:
        """构建闲鱼聊天初始化上下文。

        建连路径尽量对齐 XianYuApis：优先使用 Cookie 里的 unb 作为当前账号 ID，
        直接生成 ``UUID-unb`` 的 IM deviceId 后请求 login.token。只有 Cookie 缺少
        unb 或只是读取 profile 时，才调用 loginuser.get。这样能减少 fresh Cookie
        建连前的额外 HTTP 请求，降低会话切换/重连时被风控的概率。
        """
        profile = XianyuChatProfile(
            user_id="",
            main_user_id="",
            domain=self.chat_domain,
            display_name="",
            avatar="",
        )

        cookie_user_id = str(self._get_cookie_value(client, "unb") or "").strip()
        if cookie_user_id:
            profile.user_id = cookie_user_id
            profile.main_user_id = cookie_user_id

        should_fetch_profile = (not include_token) or not (profile.main_user_id or profile.user_id)
        if should_fetch_profile:
            try:
                user_payload = await self._execute_api(
                    client,
                    api_name=self.chat_login_user_api_name,
                    api_url=self.chat_login_user_api_url,
                    payload={},
                )
                user_data = user_payload.get("data", {})
                profile.user_id = str(user_data.get("userId") or profile.user_id or "")
                profile.main_user_id = str(
                    user_data.get("mainUserId")
                    or user_data.get("userId")
                    or profile.main_user_id
                    or ""
                )
            except Exception as exc:
                logger.debug("获取闲鱼聊天 profile 失败: %s", exc)

        bootstrap: Dict[str, Any] = {"profile": profile}
        if not include_token:
            return bootstrap

        if not (profile.main_user_id or profile.user_id):
            raise ValueError(
                self._format_chat_auth_failure(
                    reason="Cookie 中缺少 unb，且 loginuser.get 未返回账号 ID",
                    bootstrap=bootstrap,
                    cookie=self._build_cookie_header(client),
                )
            )

        device_id = self._resolve_chat_device_id(client, profile.main_user_id or profile.user_id)
        bootstrap["device_id"] = device_id

        # 熔断器：风控期间避免持续打 login.token，加重账号封禁
        now = time.monotonic()
        if self._login_token_block_until > now:
            remaining = int(self._login_token_block_until - now)
            raise ValueError(
                f"闲鱼接口已被风控拦截，正在冷却中（{remaining} 秒后重试）。"
                "请在浏览器中正常访问闲鱼几分钟后再试。"
            )

        try:
            token_payload = await self._execute_api(
                client,
                api_name=self.chat_login_token_api_name,
                api_url=self.chat_login_token_api_url,
                payload={
                    "appKey": self.chat_ws_app_key,
                    "deviceId": device_id,
                },
                extra_params={
                    # 对齐 XianYuApis 的 login.token 参数，减少与网页 IM 链路的指纹差异。
                    "spm_pre": "a21ybx.item.want.1.14ad3da6ALVq3n",
                    "log_id": "14ad3da6ALVq3n",
                },
            )
        except ValueError as exc:
            message = str(exc).strip()
            # 命中风控 → 累计失败次数，超过阈值后熔断
            if "FAIL_SYS_USER_VALIDATE" in message or "RGV587_ERROR" in message:
                self._login_token_fail_count += 1
                if self._login_token_fail_count >= self._login_token_fail_threshold:
                    self._login_token_block_until = time.monotonic() + self._login_token_block_seconds
                    logger.warning(
                        f"login.token 连续 {self._login_token_fail_count} 次风控，"
                        f"熔断 {int(self._login_token_block_seconds)} 秒"
                    )
            if "RGV587_ERROR" in message:
                raise ValueError(
                    "闲鱼聊天接口被风控拦截，请尝试在浏览器中访问闲鱼网站完成验证后重新更新 Cookie"
                ) from exc
            if "FAIL_SYS_SESSION_EXPIRED" in message:
                raise ValueError("闲鱼登录已过期，请重新登录闲鱼后更新设置页中的 Cookie") from exc
            if (
                "FAIL_SYS_USER_VALIDATE" in message
                or "闲鱼登录已过期" in message
                or "Cookie" in message
            ):
                raise ValueError(
                    self._format_chat_auth_failure(
                        reason=f"login.token 失败：{message}",
                        bootstrap=bootstrap,
                        cookie=self._build_cookie_header(client),
                    )
                ) from exc
            raise
        # 成功 → 重置失败计数
        self._login_token_fail_count = 0
        self._login_token_block_until = 0.0
        access_token = str(token_payload.get("data", {}).get("accessToken") or "")
        if not access_token:
            raise ValueError("闲鱼聊天 token 获取失败，请重新登录闲鱼后更新设置页中的 Cookie")

        bootstrap["access_token"] = access_token

        return bootstrap

    def _format_chat_auth_failure(
        self,
        reason: str,
        bootstrap: Dict[str, Any] | None = None,
        cookie: str = "",
    ) -> str:
        """生成不泄露 Cookie/token 值的聊天鉴权诊断。"""
        bootstrap = bootstrap or {}
        profile = bootstrap.get("profile")
        user_id = ""
        if isinstance(profile, XianyuChatProfile):
            user_id = str(profile.main_user_id or profile.user_id or "").strip()
        device_id = str(bootstrap.get("device_id") or "").strip()
        did_suffix = device_id.rsplit("-", 1)[-1] if "-" in device_id else ""

        cookie_map = self._parse_cookie_string(cookie or self._get_xianyu_cookie_value())
        important = ("unb", "cookie2", "sgcookie", "t", "_m_h5_tk", "_m_h5_tk_enc", "cna", "cookie17", "tracknick")
        present = [name for name in important if cookie_map.get(name)]
        missing = [name for name in ("unb", "cookie2", "sgcookie", "_m_h5_tk") if not cookie_map.get(name)]

        diagnostics = []
        if user_id:
            diagnostics.append(f"user_id={user_id}")
        if did_suffix:
            diagnostics.append(f"deviceId后缀={did_suffix}")
        diagnostics.append(f"Cookie包含={','.join(present) if present else '无关键项'}")
        if missing:
            diagnostics.append(f"缺少={','.join(missing)}")

        return (
            f"闲鱼聊天鉴权失败（{str(reason or '未知原因').strip()}）。"
            f"诊断：{'；'.join(diagnostics)}。"
            "请确认粘贴的是 www.goofish.com 登录后的完整 Cookie；"
            "如果刚更新，先在浏览器正常打开闲鱼聊天页 1-2 分钟后再重试。"
        )

    async def get_chat_session_user_info(self, session_id: str) -> Dict[str, Any]:
        """获取聊天会话买家资料（idlemessage pc.user.query），带 TTL 缓存降低风控概率。"""
        normalized = str(session_id or "").split("@", 1)[0].strip()
        if not normalized:
            return {}

        now = time.monotonic()
        cached_ts = self._chat_session_info_cache_ts.get(normalized, 0.0)
        if now - cached_ts < self._chat_session_info_cache_ttl:
            cached = self._chat_session_info_cache.get(normalized)
            if cached is not None:
                return cached

        async with self._chat_session_info_semaphore:
            cached_ts = self._chat_session_info_cache_ts.get(normalized, 0.0)
            if time.monotonic() - cached_ts < self._chat_session_info_cache_ttl:
                cached = self._chat_session_info_cache.get(normalized)
                if cached is not None:
                    return cached

            cookie = self._require_xianyu_cookie()
            try:
                async with self._create_http_client(cookie) as client:
                    result = await self._execute_api(
                        client,
                        api_name=self.chat_user_query_api_name,
                        api_url=self.chat_user_query_api_url,
                        payload={
                            "type": 0,
                            "sessionType": 1,
                            "sessionId": normalized,
                            "isOwner": False,
                        },
                    )
                    data = result.get("data") or {}
            except Exception as exc:
                self._chat_session_info_cache[normalized] = {}
                self._chat_session_info_cache_ts[normalized] = now
                logger.debug(f"get_chat_session_user_info({normalized}) failed: {exc}")
                return {}

            self._chat_session_info_cache[normalized] = data
            self._chat_session_info_cache_ts[normalized] = time.monotonic()
            return data

    async def get_peer_user_info(self, user_id: str) -> Dict[str, Any]:
        """获取买家公开信息，带 TTL 缓存 + 并发限流，避免触发风控。"""
        normalized = str(user_id or "").strip()
        if not normalized:
            return {}

        # 缓存命中（5 分钟内）
        now = time.monotonic()
        cached_ts = self._peer_info_cache_ts.get(normalized, 0.0)
        if now - cached_ts < self._peer_info_cache_ttl:
            cached = self._peer_info_cache.get(normalized)
            if cached is not None:
                return cached

        # 限流：同时最多 3 个并发请求
        async with self._peer_info_semaphore:
            # 二次检查（被并发的另一个 task 抢先填了缓存）
            cached_ts = self._peer_info_cache_ts.get(normalized, 0.0)
            if time.monotonic() - cached_ts < self._peer_info_cache_ttl:
                cached = self._peer_info_cache.get(normalized)
                if cached is not None:
                    return cached

            cookie = self._require_xianyu_cookie()
            try:
                async with self._create_http_client(cookie) as client:
                    payload = {"self": False, "userId": normalized}
                    result = await self._execute_api(
                        client,
                        api_name=self.page_head_api_name,
                        api_url=self.page_head_api_url,
                        payload=payload,
                    )
                    data = result.get("data") or {}
            except Exception as exc:
                # 失败也记缓存（短期过期），避免风控时被狂打
                self._peer_info_cache[normalized] = {}
                self._peer_info_cache_ts[normalized] = now
                logger.debug(f"get_peer_user_info({normalized}) failed: {exc}")
                return {}

            self._peer_info_cache[normalized] = data
            self._peer_info_cache_ts[normalized] = time.monotonic()
            return data

    def _map_chat_conversation(
        self,
        payload: Dict[str, Any],
        profile: XianyuChatProfile,
        peer_info_cache: Dict[str, Dict[str, Any]] | None = None,
    ) -> XianyuChatConversation:
        """映射聊天会话"""
        single = payload.get("singleChatUserConversation") or {}
        conversation = single.get("singleChatConversation") or {}
        last_wrapper = single.get("lastMessage") or {}
        last_message = last_wrapper.get("message") or {}
        extension = conversation.get("extension") or {}
        last_extension = last_message.get("extension") or {}

        cid = str(conversation.get("cid") or "")
        pair_first = str(conversation.get("pairFirst") or "")
        pair_second = str(conversation.get("pairSecond") or "")
        current_user_id = profile.main_user_id or profile.user_id
        pair_first_id = pair_first.split("@")[0] if pair_first else ""
        pair_second_id = pair_second.split("@")[0] if pair_second else ""

        if current_user_id and pair_first_id == current_user_id:
            peer_user_id = pair_second_id
        elif current_user_id and pair_second_id == current_user_id:
            peer_user_id = pair_first_id
        else:
            peer_user_id = str(extension.get("extUserId") or pair_second_id or pair_first_id)

        last_summary = self._extract_chat_message_summary(last_message)
        last_message_time = self._to_int(
            last_message.get("createAt")
            or single.get("modifyTime")
            or conversation.get("createAt")
        )
        last_sender_uid = str(last_extension.get("senderUserId") or "").split("@")[0]

        session_id = cid.split("@", 1)[0] if cid else ""
        cache = peer_info_cache or {}
        peer_info = (
            (cache.get(session_id) if session_id else None)
            or (cache.get(peer_user_id) if peer_user_id else None)
            or {}
        )
        user_info = peer_info.get("userInfo") if isinstance(peer_info.get("userInfo"), dict) else {}
        _base = (peer_info.get("module") or {}).get("base") or {} if peer_info.get("module") else {}
        peer_display_name = (
            str(user_info.get("fishNick") or "")
            or str(_base.get("displayName") or "")
            or str(extension.get(f"squadName_{peer_user_id}") or extension.get("itemTitle") or "")
        )
        if not peer_display_name and last_sender_uid == peer_user_id:
            peer_display_name = str(last_extension.get("reminderTitle") or "")
        if not peer_display_name and peer_user_id:
            peer_display_name = peer_user_id
        if not peer_display_name:
            peer_display_name = "未命名会话"

        can_send = str(conversation.get("bizType") or "") in {"1", ""}
        if peer_user_id in {"0", "-1"}:
            can_send = False

        user_ext = single.get("user_extension") or {}
        peer_ext = {}
        if isinstance(user_ext, dict):
            for uid_key, ext_data in user_ext.items():
                if isinstance(ext_data, dict) and uid_key == peer_user_id:
                    peer_ext = ext_data
                    break
                if isinstance(ext_data, dict) and uid_key == f"{peer_user_id}@goofish":
                    peer_ext = ext_data
                    break
        peer_avatar = ""
        if user_info:
            peer_avatar = self._normalize_image_url(str(user_info.get("logo") or ""))
        if not peer_avatar and _base:
            _avatar_obj = _base.get("avatar") or {}
            if isinstance(_avatar_obj, dict):
                peer_avatar = self._normalize_image_url(str(_avatar_obj.get("avatar") or ""))
            else:
                peer_avatar = self._normalize_image_url(str(_avatar_obj))
        if not peer_avatar:
            peer_avatar = self._normalize_image_url(
                str(peer_ext.get("iconUrl") or peer_ext.get("avatarUrl")
                    or peer_ext.get("headPic") or "")
            )
        if not peer_avatar and peer_user_id and peer_user_id not in {"0", "-1"}:
            peer_avatar = f"https://api.goofish.com/m/userAvatar.action?id={peer_user_id}&needHttps=1"

        mapped = XianyuChatConversation(
            cid=cid,
            session_id=cid.split("@")[0] if cid else "",
            session_type=1,
            biz_type=str(conversation.get("bizType") or ""),
            title=peer_display_name,
            peer_user_id=peer_user_id,
            peer_display_name=peer_display_name,
            peer_avatar=peer_avatar,
            item_id=str(extension.get("itemId") or ""),
            item_title=str(extension.get("itemTitle") or ""),
            item_image=self._normalize_image_url(str(extension.get("itemMainPic") or "")),
            last_message_id=str(last_message.get("messageId") or ""),
            last_message_summary=last_summary,
            last_message_time=last_message_time,
            last_message_time_text=self._format_datetime(last_message_time),
            unread_count=self._to_int(
                last_message.get("unreadCount")
                or single.get("redPoint")
                or 0
            ),
            red_point=self._to_int(single.get("redPoint")),
            top_rank=self._to_int(single.get("topRank")),
            muted=bool(single.get("muteNotification")),
            visible=bool(single.get("visible", 1)),
            can_send=can_send,
        )
        if cid:
            cache_value = {
                "item_id": mapped.item_id,
                "peer_user_id": mapped.peer_user_id,
                "item_title": mapped.item_title,
            }
            self._conversation_item_cache[cid] = cache_value
            if mapped.session_id:
                self._conversation_item_cache[mapped.session_id] = cache_value
        return mapped

    def _map_chat_message(
        self,
        payload: Dict[str, Any],
        cid: str,
        profile: XianyuChatProfile,
    ) -> XianyuChatMessage:
        """映射聊天消息"""
        message = payload.get("message") or {}
        sender = message.get("sender") or {}
        sender_uid = str(sender.get("uid") or "").split("@")[0]
        current_user_id = profile.main_user_id or profile.user_id

        content_payload = self._decode_chat_message_content(message)
        content_type = self._extract_chat_message_type(message, content_payload)
        summary = self._extract_chat_message_summary(message, content_payload)
        text = self._extract_chat_message_text(message, content_payload, summary)
        image_url = self._extract_chat_message_image(content_payload)
        create_at = self._to_int(message.get("createAt"))

        return XianyuChatMessage(
            cid=cid,
            message_id=str(message.get("messageId") or ""),
            numeric_message_id=self._extract_numeric_message_id(message.get("messageId")),
            sender_uid=sender_uid,
            sender_display_name=profile.display_name if sender_uid == current_user_id else "",
            direction="out" if sender_uid == current_user_id else "in",
            content_type=content_type,
            summary=summary,
            text=text,
            image_url=image_url,
            create_at=create_at,
            create_at_text=self._format_datetime(create_at),
            read_status=self._to_int(payload.get("readStatus")),
            raw_extension={
                key: str(value)
                for key, value in (message.get("extension") or {}).items()
                if value is not None
            },
        )

    def _require_xianyu_cookie(self) -> str:
        cookie = self._get_xianyu_cookie_value()
        if not cookie:
            raise ValueError("请先在设置页配置闲鱼 Cookie")
        return cookie

    def _create_http_client(self, cookie: str) -> httpx.AsyncClient:
        client = httpx.AsyncClient(
            headers=self.default_headers,
            timeout=20.0,
            follow_redirects=True,
        )
        for name, value in self._parse_cookie_string(cookie).items():
            client.cookies.set(name, value, domain=".goofish.com")
        return client

    def _ensure_chat_rpc_success(self, payload: Dict[str, Any], fallback: str) -> None:
        if payload.get("code") == 200:
            return

        body = payload.get("body") or {}
        if isinstance(body, dict):
            for key in ("reason", "developerMessage", "code"):
                message = str(body.get(key) or "").strip()
                if message:
                    raise ValueError(message)
        raise ValueError(fallback)

    def _load_chat_device_map(self) -> Dict[str, str]:
        try:
            if not self._chat_device_store_path.exists():
                return {}
            payload = json.loads(self._chat_device_store_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return {}
            return {str(key): str(value) for key, value in payload.items() if key and value}
        except Exception:
            return {}

    def _save_chat_device_map(self, device_map: Dict[str, str]) -> None:
        write_json_atomic(self._chat_device_store_path, device_map)

    def _is_chat_device_id_for_user(self, device_id: str, user_id: str) -> bool:
        normalized_user = str(user_id or "").strip()
        text = str(device_id or "").strip()
        if not normalized_user or not text:
            return False
        prefix, sep, suffix = text.rpartition("-")
        if sep != "-" or suffix != normalized_user:
            return False
        # UUID 主体应为 36 位（参考 XianYuApis: random UUID + "-" + unb）。
        # 对字符集保持宽松，兼容历史生成器的大小写/数字。
        return len(prefix) == 36

    def _build_chat_device_id(self, user_id: str, *, persist: bool = True) -> str:
        """获取账号级 IM deviceId。

        XianYuApis 的实现是在实例初始化时生成 ``random-uuid + "-" + unb`` 并复用。
        本项目服务会重启，所以把该值按 unb 持久化；避免每次切换会话/重启后 deviceId
        漂移，也避免错误复用扫码登录的 cna/device 指纹。
        """
        normalized = str(user_id or "0").strip() or "0"
        if persist:
            device_map = self._load_chat_device_map()
            existing = str(device_map.get(normalized) or "").strip()
            if self._is_chat_device_id_for_user(existing, normalized):
                return existing

            generated = f"{uuid.uuid4()}-{normalized}"
            device_map[normalized] = generated
            with contextlib.suppress(Exception):
                self._save_chat_device_map(device_map)
            return generated

        # 兜底：如果运行态配置目录不可写，用确定性值保证同账号本进程/测试稳定。
        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        digest = hashlib.sha256(f"xianyu-device:{normalized}".encode("utf-8")).digest()
        parts = []
        for i in range(36):
            if i in (8, 13, 18, 23):
                parts.append("-")
            elif i == 14:
                parts.append("4")
            else:
                value = digest[i % len(digest)] & 0x0F
                if i == 19:
                    value = (value & 0x03) | 0x08
                parts.append(chars[value])
        return "".join(parts) + "-" + normalized

    def _resolve_chat_device_id(self, client: httpx.AsyncClient, user_id: str) -> str:
        """解析聊天 IM deviceId（格式：UUID-userId）。

        只复用“本身就是 IM deviceId 且后缀匹配 unb”的指纹；扫码/浏览器登录指纹
        里的 deviceId/cna 不再直接用于 login.token，避免和账号 unb 不匹配触发风控。
        """
        cookie_user_id = str(self._get_cookie_value(client, "unb") or "").strip()
        normalized_user_id = cookie_user_id or str(user_id or "").strip()

        fingerprint = getattr(self.auth_login, "fingerprint", {}) or {}
        if isinstance(fingerprint, dict) and normalized_user_id:
            fingerprint_device_id = str(fingerprint.get("deviceId") or "").strip()
            if self._is_chat_device_id_for_user(fingerprint_device_id, normalized_user_id):
                return fingerprint_device_id

        if normalized_user_id:
            return self._build_chat_device_id(normalized_user_id)

        return self._build_chat_device_id("0")

    def _generate_message_uuid(self) -> str:
        return f"-{int(time.time() * 1000)}{uuid.uuid4().hex[:10]}"

    def _build_chat_sdk_user_agent(self) -> str:
        browser_user_agent = self.default_headers["user-agent"]
        if "DingWeb/" in browser_user_agent:
            return browser_user_agent

        browser_name = "other"
        browser_version = "other"
        if "Chrome/" in browser_user_agent:
            browser_name = "Chrome"
            browser_version = browser_user_agent.split("Chrome/", 1)[1].split(" ", 1)[0]
        elif "Safari/" in browser_user_agent:
            browser_name = "Safari"
            browser_version = browser_user_agent.split("Version/", 1)[1].split(" ", 1)[0] if "Version/" in browser_user_agent else "other"

        os_name = "other"
        os_version = "other"
        if "Mac OS X " in browser_user_agent:
            os_name = "Mac OS"
            os_version = browser_user_agent.split("Mac OS X ", 1)[1].split(")", 1)[0].replace("_", ".")
        elif "Windows NT " in browser_user_agent:
            os_name = "Windows"
            os_version = browser_user_agent.split("Windows NT ", 1)[1].split(";", 1)[0]

        sdk_version = self.chat_sdk_version
        return (
            f"{browser_user_agent} "
            f"DingTalk({sdk_version}) "
            f"OS({os_name}/{os_version}) "
            f"Browser({browser_name}/{browser_version}) "
            f"DingWeb/{sdk_version} "
            f"IMPaaS "
            f"DingWeb/{sdk_version}"
        )

    def _normalize_chat_uid(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return text if "@" in text else f"{text}@{self.chat_domain}"

    async def _get_chat_conversation_payload(
        self,
        chat_client: XianyuChatWsClient,
        cid: str,
    ) -> Dict[str, Any]:
        response = await chat_client.send_rpc("/r/Conversation/getByCids", [[cid]])
        self._ensure_chat_rpc_success(response, "获取会话详情失败")

        for item in response.get("body") or []:
            if not isinstance(item, dict):
                continue
            single = item.get("singleChatUserConversation") or {}
            conversation = single.get("singleChatConversation") or {}
            if str(conversation.get("cid") or "") == cid:
                return item
        raise ValueError("未找到对应会话，请刷新后重试")

    def _build_chat_send_payloads(
        self,
        cid: str,
        text: str,
        conversation_payload: Dict[str, Any],
        profile: XianyuChatProfile,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        single = conversation_payload.get("singleChatUserConversation") or {}
        conversation = single.get("singleChatConversation") or {}
        extension = {
            key: str(value)
            for key, value in (conversation.get("extension") or {}).items()
            if value is not None
        }

        pair_first = self._normalize_chat_uid(str(conversation.get("pairFirst") or ""))
        pair_second = self._normalize_chat_uid(str(conversation.get("pairSecond") or ""))
        current_user_id = str(profile.main_user_id or profile.user_id or "")
        current_uid = self._normalize_chat_uid(current_user_id)

        pair_first_id = pair_first.split("@", 1)[0] if pair_first else ""
        pair_second_id = pair_second.split("@", 1)[0] if pair_second else ""

        receiver_uid = ""
        if current_user_id and pair_first_id == current_user_id:
            receiver_uid = pair_second
        elif current_user_id and pair_second_id == current_user_id:
            receiver_uid = pair_first
        elif pair_second:
            receiver_uid = pair_second
        elif pair_first:
            receiver_uid = pair_first

        msg_read_status_setting = self._to_int(conversation.get("msgReadStatusSetting") or 1) or 1
        actual_receivers = [receiver_uid, current_uid] if receiver_uid and current_uid else ([receiver_uid] if receiver_uid else [])

        message_payload = {
            "uuid": self._generate_message_uuid(),
            "cid": cid,
            "conversationType": 1,
            "content": {
                "contentType": 101,
                "custom": {
                    "type": 1,
                    "data": self._encode_chat_text(text),
                },
            },
            "redPointPolicy": 0,
            "extension": {"extJson": "{}"},
            "ctx": {"appVersion": "1.0", "platform": "web"},
            "mtags": {},
            "msgReadStatusSetting": msg_read_status_setting,
        }

        conversation_options: Dict[str, Any] = {}
        if current_uid:
            conversation_options[current_uid] = {
                "extension": {
                    key: str(value)
                    for key, value in (single.get("user_extension") or {}).items()
                    if value is not None
                },
                "hide": 0 if bool(single.get("visible", 1)) else 1,
                "redPoint": self._to_int(single.get("redPoint")),
                "mute": 1 if bool(single.get("muteNotification")) else 0,
                "utags": {},
            }
        if receiver_uid and receiver_uid not in conversation_options:
            conversation_options[receiver_uid] = {
                "extension": {},
                "hide": 0,
                "redPoint": 0,
                "mute": 0,
                "utags": {},
            }

        send_options: Dict[str, Any] = {
            "createSingleChatCoversation": {
                "cid": cid,
                "pairFirst": pair_first,
                "pairSecond": pair_second,
                "bizType": str(conversation.get("bizType") or ""),
                "extension": extension,
                "ctx": {},
            },
            "createSingleChatConversationOption": {
                "options": conversation_options,
                "ctags": {},
                "msgReadStatusSetting": msg_read_status_setting,
            },
            "receiverOption": {
                "defaultMessageUserOption": {
                    "extension": {},
                    "receiveType": 0,
                }
            },
        }

        if actual_receivers:
            send_options["actualReceivers"] = actual_receivers
            send_options["receiverScope"] = {
                "actualReceivers": actual_receivers,
                "isShare": False,
                "excludeReceivers": [],
            }
            send_options["receiverOption"]["messageUserOptions"] = {
                receiver_uid: {
                    "extension": {},
                    "receiveType": 0,
                }
            }

        return message_payload, send_options

    def _build_chat_send_option_fallbacks(self, send_options: Dict[str, Any]) -> List[Dict[str, Any]]:
        fallbacks: List[Dict[str, Any]] = [send_options]
        actual_receivers = send_options.get("actualReceivers") or []
        receiver_scope = send_options.get("receiverScope") or {}

        if actual_receivers:
            fallbacks.append({"actualReceivers": actual_receivers})
        if receiver_scope:
            fallbacks.append({"receiverScope": receiver_scope})
        fallbacks.append({})

        normalized: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in fallbacks:
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(item)
        return normalized

    def _build_chat_send_result(
        self,
        cid: str,
        summary: str,
        payload: Dict[str, Any],
    ) -> XianyuChatSendResult:
        body = payload.get("body") or {}
        return XianyuChatSendResult(
            cid=cid,
            message_id=str(body.get("messageId") or ""),
            uuid=str(body.get("uuid") or ""),
            create_at=self._to_int(body.get("createAt")),
            summary=summary,
        )

    def _normalize_message_cursor(self, cursor: str | None) -> int:
        if cursor:
            numeric = self._extract_numeric_message_id(cursor)
            if numeric > 0:
                return numeric
        return self._to_int(self.chat_message_start_cursor)

    def _extract_numeric_message_id(self, value) -> int:
        if value in (None, ""):
            return 0
        text = str(value)
        number_text = text.split(".", 1)[0]
        try:
            return int(number_text)
        except (TypeError, ValueError):
            return 0

    def _decode_chat_message_content(self, message: Dict[str, Any]) -> Dict[str, Any]:
        content = message.get("content") or {}
        custom = content.get("custom") or {}
        encoded = str(custom.get("data") or "").strip()
        if not encoded:
            return {}

        padding = "=" * (-len(encoded) % 4)
        try:
            decoded = base64.b64decode(encoded + padding).decode("utf-8")
            return json.loads(decoded)
        except Exception:
            return {}

    def _extract_chat_message_type(
        self,
        message: Dict[str, Any],
        content_payload: Dict[str, Any],
    ) -> int:
        content = message.get("content") or {}
        custom = content.get("custom") or {}
        return self._to_int(
            content_payload.get("contentType")
            or custom.get("type")
            or content.get("contentType")
            or 0
        )

    def _extract_chat_message_summary(
        self,
        message: Dict[str, Any],
        content_payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        content = message.get("content") or {}
        custom = content.get("custom") or {}
        summary = str(custom.get("summary") or "").strip()
        if summary:
            return summary

        text = self._extract_chat_message_text(message, content_payload or {}, "")
        if text:
            return text

        extension = message.get("extension") or {}
        return str(extension.get("detailNotice") or extension.get("reminderContent") or "").strip()

    def _extract_chat_message_text(
        self,
        message: Dict[str, Any],
        content_payload: Dict[str, Any],
        fallback: str,
    ) -> str:
        content_type = self._extract_chat_message_type(message, content_payload)
        if content_type == 1:
            text_payload = content_payload.get("text") or {}
            text = str(text_payload.get("text") or text_payload.get("content") or "").strip()
            if text:
                return text

        if fallback:
            return fallback

        mapping = {
            2: "[图片]",
            14: "[系统消息]",
            26: "[卡片消息]",
            40: "[AI消息]",
        }
        return mapping.get(content_type, "")

    def _extract_chat_message_image(self, content_payload: Dict[str, Any]) -> str:
        image = content_payload.get("image") or {}
        pics = image.get("pics") or []
        if not pics:
            return ""
        first = pics[0] or {}
        return self._normalize_image_url(str(first.get("url") or ""))

    def _extract_filters(self, result_info: Dict) -> List[XianyuFilterGroup]:
        """提取筛选项"""
        tab_list = (
            result_info.get("sqiControlFields", {})
            .get("cpvNavigatorDo", {})
            .get("tabList", [])
        )
        groups: List[XianyuFilterGroup] = []
        for tab in tab_list[:4]:
            pid = str(tab.get("pid") or "")
            options = []
            for option in tab.get("pvTermList", [])[:10]:
                vid = str(option.get("vid") or "")
                if not pid or not vid:
                    continue
                options.append(
                    XianyuFilterOption(
                        label=str(option.get("vname") or ""),
                        value=vid,
                        checked=bool(option.get("checked")),
                    )
                )

            if pid and options:
                groups.append(
                    XianyuFilterGroup(
                        name=str(tab.get("pname") or ""),
                        pid=pid,
                        options=options,
                    )
                )
        return groups

    def _extract_items(self, result_list: List[Dict]) -> List[XianyuSearchItem]:
        """提取搜索结果项"""
        items: List[XianyuSearchItem] = []
        for entry in result_list:
            ex_content = (
                entry.get("data", {})
                .get("item", {})
                .get("main", {})
                .get("exContent", {})
            )
            item_id = str(ex_content.get("itemId") or "")
            if not item_id:
                continue

            tags = [
                str(tag.get("data", {}).get("content") or "")
                for tag in ex_content.get("fishTags", {}).get("r3", {}).get("tagList", [])
                if tag.get("data", {}).get("content")
            ]

            items.append(
                XianyuSearchItem(
                    item_id=item_id,
                    title=str(ex_content.get("title") or ""),
                    price=self._extract_price_text(ex_content.get("price", []), ex_content),
                    image=self._normalize_image_url(str(ex_content.get("picUrl") or "")),
                    area=str(ex_content.get("area") or ""),
                    seller=str(
                        ex_content.get("userNickName")
                        or ex_content.get("detailParams", {}).get("userNick")
                        or ""
                    ),
                    seller_avatar=self._normalize_image_url(str(ex_content.get("userAvatarUrl") or "")),
                    want=str(ex_content.get("want") or ""),
                    tags=tags,
                    detail_url=f"https://www.goofish.com/item?id={item_id}",
                )
            )
        return items

    def _extract_price_text(self, price_nodes: List[Dict], ex_content: Dict) -> str:
        """提取价格文本"""
        if price_nodes:
            parts = [str(node.get("text") or "") for node in price_nodes]
            value = "".join(parts).strip()
            if value:
                return value

        detail_price = ex_content.get("detailParams", {}).get("soldPrice")
        if detail_price:
            return f"¥{detail_price}"
        return ""

    def _parse_cookie_string(self, cookie_string: str) -> Dict[str, str]:
        """将浏览器 Cookie 字符串转换为字典"""
        parsed: Dict[str, str] = {}
        for segment in cookie_string.split(";"):
            item = segment.strip()
            if not item or "=" not in item:
                continue
            key, value = item.split("=", 1)
            parsed[key.strip()] = value.strip()
        return parsed

    def _sync_runtime_cookie(self, client: httpx.AsyncClient) -> None:
        """同步运行时 Cookie。

        除 mtop token 外，也保留聊天鉴权相关 Cookie，避免刷新 token 后持久化配置
        仍停留在旧 cookie2/sgcookie/t，导致聊天 WS 和自动回复链路失效。
        """
        current_cookie = self._parse_cookie_string(self._get_xianyu_cookie_value())
        refreshed = False
        for key in ("cookie2", "sgcookie", "t", "_m_h5_tk", "_m_h5_tk_enc", "mtop_partitioned_detect"):
            value = self._get_cookie_value(client, key)
            if value:
                current_cookie[key] = value
                refreshed = True

        if refreshed:
            normalized = "; ".join(f"{key}={value}" for key, value in current_cookie.items())
            app_settings.cookies.xianyu = normalized
            save_xianyu_cookie_string(normalized, source="runtime_refresh")

    def _get_sign_token(self, client: httpx.AsyncClient) -> str:
        """从 Cookie 中提取签名 token"""
        raw = self._get_cookie_value(client, "_m_h5_tk")
        return raw.split("_", 1)[0] if raw else ""

    def _build_sign(self, token: str, timestamp: str, data_json: str) -> str:
        """生成 mtop 签名"""
        plain = f"{token}&{timestamp}&{self.app_key}&{data_json}"
        return hashlib.md5(plain.encode("utf-8")).hexdigest()

    def _is_success(self, payload: Dict) -> bool:
        return any(str(item).startswith("SUCCESS::") for item in payload.get("ret", []))

    def _is_token_expired(self, payload: Dict) -> bool:
        return any("FAIL_SYS_TOKEN_EXOIRED" in str(item) for item in payload.get("ret", []))

    def _extract_error(self, payload: Dict) -> str:
        ret = payload.get("ret", [])
        if ret:
            return "; ".join(str(item) for item in ret if item)
        return "闲鱼接口请求失败"

    def _to_int(self, value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _format_detail_price(self, value) -> str:
        if value in (None, "", "0"):
            return ""
        text = str(value).strip()
        return text if text.startswith("¥") else f"¥{text}"

    def _format_transport_fee(self, value) -> str:
        if value in (None, "", "0", "0.0", "0.00"):
            return "包邮"
        text = str(value).strip()
        return text if text.startswith("¥") else f"运费 ¥{text}"

    def _dedupe_texts(self, values: List[str]) -> List[str]:
        result: List[str] = []
        seen = set()
        for value in values:
            text = value.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def _format_datetime(self, value) -> str:
        if not value:
            return ""
        try:
            timestamp = int(value) / 1000
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
        except (TypeError, ValueError, OSError):
            return ""

    def _extract_first_url(self, text: str) -> str:
        match = re.search(r"https?://[^\s，,。)）]+", str(text or ""))
        return match.group(0) if match else ""

    def _normalize_image_url(self, url: str) -> str:
        url = str(url or "").strip()
        if url.startswith("http://"):
            return "https://" + url[len("http://"):]
        return url

    def _get_cookie_value(self, client: httpx.AsyncClient, name: str) -> str:
        """从 cookie jar 中取最后一个同名值"""
        value = ""
        for cookie in client.cookies.jar:
            if cookie.name == name:
                value = cookie.value
        return value

    def _build_cookie_header(self, client: httpx.AsyncClient) -> str:
        """构建 Cookie header 字符串，从 httpx cookie jar 读取"""
        seen: Dict[str, str] = {}
        for cookie in client.cookies.jar:
            seen[cookie.name] = cookie.value
        return "; ".join(f"{k}={v}" for k, v in seen.items())

    def _extract_token_cookies(self, client: httpx.AsyncClient, response: httpx.Response) -> None:
        """合并响应 cookie 到 jar，参照 XianYuApis 删除同名空域旧值防止冲突"""
        response_cookie_names = set(response.cookies.keys())
        existing_cookie_names = set(c.name for c in client.cookies.jar)
        for name in response_cookie_names & existing_cookie_names:
            for cookie in list(client.cookies.jar):
                if cookie.name == name and cookie.domain == "" and cookie.path == "/":
                    client.cookies.jar.clear(cookie.domain, cookie.path, cookie.name)
                    break

    async def _refresh_token_via_index(self, client: httpx.AsyncClient) -> None:
        """参照 XianYuApis，通过 index API 刷新 _m_h5_tk"""
        url = self.index_api_url
        params = {
            "jsv": "2.7.2",
            "appKey": self.app_key,
            "type": "originaljson",
            "dataType": "json",
        }

        for attempt_url in [url, "https://www.goofish.com/", url]:
            p = params if "h5api" in attempt_url else None
            try:
                if p:
                    resp = await client.get(attempt_url, params=p)
                else:
                    resp = await client.get(attempt_url)
                self._extract_token_cookies(client, resp)
                if self._get_cookie_value(client, "_m_h5_tk"):
                    self._log.info("Token 刷新成功，_m_h5_tk 已更新")
                    break
            except Exception:
                self._log.debug("Token 刷新尝试失败: %s", attempt_url)

    # ============================================================
    # 闲鱼商品管理 / 自动发货模块
    # ============================================================

    def _map_manage_item(self, raw: Dict[str, Any]) -> dict[str, Any]:
        """从远程 cardData 映射到本地存储格式"""
        price_info = raw.get("priceInfo") if isinstance(raw.get("priceInfo"), dict) else {}
        pic_info = raw.get("picInfo") if isinstance(raw.get("picInfo"), dict) else {}
        item_id = str(raw.get("id") or raw.get("itemId") or "").strip()
        return {
            "item_id": item_id,
            "item_title": str(raw.get("title") or "").strip(),
            "item_price": str(price_info.get("price") or raw.get("price") or "").strip(),
            "item_image": self._normalize_image_url(str(pic_info.get("picUrl") or raw.get("picUrl") or "")),
            "item_status": str(raw.get("itemStatus") or raw.get("itemStatusStr") or "").strip(),
            "item_detail": str(raw.get("item_detail") or ""),
            "multi_quantity_delivery": bool(raw.get("multi_quantity_delivery") or False),
        }

    _ORDER_STATUS_GROUP_MAP = {
        "待发货": "pending_ship",
        "部分发货": "pending_ship",
        "待付款": "pending_payment",
        "处理中": "processing",
        "已发货": "shipped",
        "部分待收尾": "shipped",
        "交易成功": "completed",
        "已完成": "completed",
        "退款中": "refunding",
        "退款撤销": "cancelled",
        "交易关闭": "cancelled",
        "已关闭": "cancelled",
    }

    def _map_merchant_order(self, raw: Dict[str, Any]) -> Optional[XianyuOrder]:
        common = raw.get("commonData") if isinstance(raw.get("commonData"), dict) else {}
        buyer = raw.get("buyerInfoVO") if isinstance(raw.get("buyerInfoVO"), dict) else {}
        price = raw.get("priceVO") if isinstance(raw.get("priceVO"), dict) else {}
        item = raw.get("itemInfoVO") if isinstance(raw.get("itemInfoVO"), dict) else {}

        order_id = str(common.get("orderId") or "").strip()
        if not order_id:
            return None

        status_text = str(common.get("orderStatus") or "").strip()
        status_group = self._ORDER_STATUS_GROUP_MAP.get(status_text, "unknown")

        item_title = str(item.get("title") or common.get("itemTitle") or "").strip()
        item_image = self._normalize_image_url(str(item.get("picUrl") or common.get("itemPic") or ""))
        item_price = str(item.get("price") or price.get("auctionPrice") or "").strip()

        amount_text = ""
        for candidate in (price.get("totalPrice"), price.get("confirmFee"), price.get("auctionPrice")):
            text = str(candidate or "").strip()
            if text:
                amount_text = text
                break

        is_dummy = bool(item.get("isDummy") or common.get("isDummy") or raw.get("isDummy"))
        quantity_raw = common.get("quantity") or item.get("quantity") or raw.get("quantity") or 1
        try:
            quantity = int(quantity_raw)
        except (TypeError, ValueError):
            quantity = 1

        return XianyuOrder(
            order_id=order_id,
            item_id=str(common.get("itemId") or item.get("itemId") or "").strip(),
            item_title=item_title,
            item_image=item_image,
            item_price=item_price,
            buyer_id=str(buyer.get("buyerId") or "").strip(),
            buyer_nick=str(buyer.get("userNick") or "").strip(),
            buyer_avatar=self._normalize_image_url(str(buyer.get("avatar") or "")),
            amount=amount_text,
            status_code=str(common.get("orderStatusCode") or "").strip(),
            status_text=status_text,
            status_group=status_group,
            created_at=str(common.get("createTime") or "").strip(),
            paid_at=str(common.get("paySuccessTime") or "").strip(),
            finished_at=str(common.get("finishTime") or "").strip(),
            is_dummy=is_dummy,
            quantity=quantity,
            remark=str(common.get("buyerMessage") or buyer.get("buyerMemo") or "").strip(),
        )

    async def list_merchant_orders(
        self,
        page: int = 1,
        page_size: int = 20,
        status: str = "ALL",
        order_id_query: str = "",
    ) -> XianyuOrderPage:
        """获取当前账号的卖家订单列表"""
        page = max(int(page or 1), 1)
        page_size = max(min(int(page_size or 20), 50), 1)
        query_code = (status or "ALL").strip().upper() or "ALL"

        cookie = self._get_xianyu_cookie_value()
        if not cookie:
            raise ValueError("请先在设置页配置闲鱼 Cookie")

        async with httpx.AsyncClient(
            headers=self.default_headers,
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            for name, value in self._parse_cookie_string(cookie).items():
                client.cookies.set(name, value, domain=".goofish.com")

            if not self._get_cookie_value(client, "_m_h5_tk"):
                await self._warmup_token(client)
            await self._refresh_login_state(client)

            payload = {
                "pageNumber": page,
                "rowsPerPage": page_size,
                "orderIds": order_id_query.strip(),
                "queryCode": query_code,
                "orderSearchParam": "{}",
            }
            response_data = await self._execute_api(
                client,
                api_name=self.merchant_order_list_api_name,
                api_url=self.merchant_order_list_api_url,
                payload=payload,
                extra_params={
                    "valueType": "string",
                    "spm_cnt": "a21107h.42831410.0.0",
                },
                extra_headers={
                    "idle_site_biz_code": self.merchant_order_biz_code,
                    "idle_user_group_member_id": "",
                    "origin": "https://seller.goofish.com",
                    "referer": self.merchant_order_referer,
                },
            )

        module = ((response_data.get("data") or {}).get("module") or {})
        raw_items = module.get("items") or []
        if not isinstance(raw_items, list):
            raw_items = []

        orders = [self._map_merchant_order(item) for item in raw_items if isinstance(item, dict)]
        orders = [order for order in orders if order is not None]

        has_more = str(module.get("nextPage") or "").lower() == "true"
        total_text = str(module.get("totalCount") or "").strip()
        try:
            total = int(total_text) if total_text.isdigit() else len(orders)
        except (TypeError, ValueError):
            total = len(orders)

        return XianyuOrderPage(
            orders=orders,
            page=page,
            page_size=page_size,
            total=total,
            has_more=has_more,
        )

    async def ship_merchant_order(
        self,
        order_id: str,
        trade_text: str = "",
    ) -> XianyuOrderShipResult:
        """提交虚拟商品自动发货（mtop.taobao.idle.logistic.consign.dummy）"""
        order_id = (order_id or "").strip()
        if not order_id:
            raise ValueError("订单号不能为空")

        cookie = self._get_xianyu_cookie_value()
        if not cookie:
            raise ValueError("请先在设置页配置闲鱼 Cookie")

        async with httpx.AsyncClient(
            headers=self.default_headers,
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            for name, value in self._parse_cookie_string(cookie).items():
                client.cookies.set(name, value, domain=".goofish.com")

            if not self._get_cookie_value(client, "_m_h5_tk"):
                await self._warmup_token(client)
            await self._refresh_login_state(client)

            payload = {
                "orderId": order_id,
                "tradeText": trade_text or "",
                "picList": [],
                "newUnconsign": True,
            }
            await self._execute_api(
                client,
                api_name=self.merchant_order_ship_api_name,
                api_url=self.merchant_order_ship_api_url,
                payload=payload,
                extra_headers={
                    "idle_site_biz_code": self.merchant_order_biz_code,
                    "origin": "https://seller.goofish.com",
                    "referer": self.merchant_order_referer,
                },
            )

        logger.info(f"订单已完成虚拟发货：order={order_id}")
        return XianyuOrderShipResult(order_id=order_id, success=True, message="虚拟发货成功")

    def list_manage_items(self, page: int = 1, page_size: int = 20) -> XianyuManageItemPage:
        return self.item_store.list_items(page=page, page_size=page_size)

    async def sync_manage_items_page(self, page: int = 1, page_size: int = 20) -> XianyuManageItemPage:
        page = max(int(page or 1), 1)
        page_size = max(min(int(page_size or 20), 100), 1)
        cookie = self._get_xianyu_cookie_value()
        if not cookie:
            raise ValueError("请先在设置页配置闲鱼 Cookie")

        async with self._create_http_client(cookie) as client:
            if not self._get_cookie_value(client, "_m_h5_tk"):
                await self._warmup_token(client)
            await self._refresh_login_state(client)
            user_id = str(self._get_cookie_value(client, "unb") or "").strip()
            if not user_id:
                profile = await self.get_chat_profile()
                user_id = str(profile.main_user_id or profile.user_id or "").strip()
            payload = {
                "needGroupInfo": False,
                "pageNumber": page,
                "pageSize": page_size,
                "groupName": "在售",
                "groupId": "58877261",
                "defaultGroup": True,
                "userId": user_id,
            }
            response_data = await self._execute_api(
                client,
                api_name=self.manage_item_list_api_name,
                api_url=self.manage_item_list_api_url,
                payload=payload,
                extra_params={
                    "spm_cnt": "a21ybx.im.0.0",
                    "spm_pre": "a21ybx.collection.menu.1.272b5141NafCNK",
                },
            )

        data = response_data.get("data") or {}
        card_list = data.get("cardList") or []
        if not isinstance(card_list, list):
            card_list = []
        mapped_items = [
            self._map_manage_item((card or {}).get("cardData") or {})
            for card in card_list
            if isinstance((card or {}).get("cardData"), dict)
        ]
        mapped_items = [item for item in mapped_items if item.get("item_id")]
        self.item_store.upsert_items(mapped_items)
        synced_items = [
            stored_item
            for stored_item in (
                self.item_store.get_item(str(item.get("item_id") or "").strip())
                for item in mapped_items
            )
            if stored_item is not None
        ]
        store_total = self.item_store.list_items(page=1, page_size=1).total
        module = data.get("module") if isinstance(data.get("module"), dict) else {}
        raw_next_page = (
            data.get("nextPage")
            if "nextPage" in data
            else module.get("nextPage")
        )
        remote_has_more = bool(raw_next_page) if isinstance(raw_next_page, bool) else str(raw_next_page or "").lower() == "true"
        total_text = str(data.get("totalCount") or module.get("totalCount") or "").strip()
        try:
            remote_total = int(total_text) if total_text.isdigit() else store_total
        except (TypeError, ValueError):
            remote_total = store_total
        if not raw_next_page and remote_total > page * page_size:
            remote_has_more = True
        return XianyuManageItemPage(
            items=synced_items,
            total=max(remote_total, store_total, ((page - 1) * page_size) + len(mapped_items)),
            page=page,
            page_size=page_size,
            has_more=remote_has_more,
        )

    async def sync_manage_items_all(self) -> dict[str, int]:
        page = 1
        pages = 0
        synced = 0
        while True:
            before_total = self.item_store.list_items(page=1, page_size=1).total
            current = await self.sync_manage_items_page(page=page, page_size=20)
            after_total = self.item_store.list_items(page=1, page_size=1).total
            pages += 1
            synced += max(after_total - before_total, 0)
            if not current.has_more:
                break
            if not current.items and after_total == before_total:
                break
            page += 1
        return {"synced": synced, "pages": pages}

    def get_manage_item(self, item_id: str) -> XianyuManageItem:
        item = self.item_store.get_item(item_id)
        if item is None:
            raise ValueError("商品不存在")
        return item

    def update_manage_item(self, item_id: str, item_detail: str) -> XianyuManageItem:
        item = self.item_store.update_item(item_id, item_detail=item_detail)
        if item is None:
            raise ValueError("商品不存在")
        return item

    def set_manage_item_multi_quantity_delivery(self, item_id: str, enabled: bool) -> XianyuManageItem:
        item = self.item_store.set_multi_quantity_delivery(item_id, enabled)
        if item is None:
            raise ValueError("商品不存在")
        return item

    def delete_manage_item(self, item_id: str) -> bool:
        return self.item_store.delete_item(item_id)

    async def polish_manage_item(self, item_id: str, enable_notification: bool = False) -> dict[str, Any]:
        """擦亮单个商品（调用 mtop.taobao.idle.item.polish）"""
        item_id = (item_id or "").strip()
        if not item_id:
            raise ValueError("商品 ID 不能为空")

        cookie = self._get_xianyu_cookie_value()
        if not cookie:
            raise ValueError("请先在设置页配置闲鱼 Cookie")

        async with httpx.AsyncClient(
            headers=self.default_headers,
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            for name, value in self._parse_cookie_string(cookie).items():
                client.cookies.set(name, value, domain=".goofish.com")

            if not self._get_cookie_value(client, "_m_h5_tk"):
                await self._warmup_token(client)
            await self._refresh_login_state(client)

            params = {
                "jsv": "2.7.2",
                "appKey": self.app_key,
                "t": str(int(time.time()) * 1000),
                "sign": "",
                "v": "1.0",
                "type": "originaljson",
                "accountSite": "xianyu",
                "dataType": "json",
                "timeout": "20000",
                "api": self.item_polish_api_name,
                "sessionOption": "AutoLoginOnly",
                "spm_cnt": "a21ybx.im.0.0",
                "spm_pre": "a21ybx.collection.menu.1.272b5141NafCNK",
            }
            data_val = json.dumps({"itemId": item_id}, separators=(",", ":"))
            sign = self._build_sign(str(params["t"]), self._get_sign_token(client), data_val)
            params["sign"] = sign

            try:
                response = await client.post(
                    self.item_polish_api_url,
                    params=params,
                    data={"data": data_val},
                )
                response.raise_for_status()
                result = response.json()

                if self._is_success(result):
                    if enable_notification:
                        self._log.info("商品擦亮成功：item_id=%s", item_id)
                    self.item_store.polish_item(item_id)
                    return {"success": True, "item_id": item_id, "message": "商品擦亮成功"}
                else:
                    error_msg = self._extract_error(result)
                    raise ValueError(f"商品擦亮失败: {error_msg}")

            except httpx.HTTPStatusError as e:
                raise ValueError(f"商品擦亮请求失败: {e.response.status_code} - {e.response.text[:200]}")
            except Exception as e:
                raise ValueError(f"商品擦亮异常: {str(e)}")

    async def polish_all_manage_items(self) -> dict[str, int]:
        """擦亮所有本地缓存的商品"""
        try:
            await self.sync_manage_items_all()
        except Exception as e:
            self._log.warning("擦亮全部商品时同步列表失败，继续执行: %s", e)

        result = self.item_store.polish_all_items()
        return {"total": result.get("total", 0), "polished": result.get("polished", 0)}

    def list_delivery_rules(self) -> list[XianyuDeliveryRule]:
        return self.delivery_store.list_rules()

    def create_delivery_rule(self, request: XianyuDeliveryRuleCreateRequest) -> XianyuDeliveryRule:
        rule = self.delivery_store.create_rule(request)
        self._sync_chat_ai_listener_state()
        return rule

    def update_delivery_rule(self, rule_id: str, request: XianyuDeliveryRuleUpdateRequest) -> XianyuDeliveryRule:
        rule = self.delivery_store.update_rule(rule_id, request.model_dump(exclude_none=True))
        if rule is None:
            raise ValueError("规则不存在")
        self._sync_chat_ai_listener_state()
        return rule

    def delete_delivery_rule(self, rule_id: str) -> bool:
        deleted = self.delivery_store.delete_rule(rule_id)
        self._sync_chat_ai_listener_state()
        return deleted

    def toggle_delivery_rule(self, rule_id: str) -> XianyuDeliveryRule:
        rule = self.delivery_store.toggle_rule(rule_id)
        if rule is None:
            raise ValueError("规则不存在")
        self._sync_chat_ai_listener_state()
        return rule

    def get_delivery_runtime_status(self) -> XianyuDeliveryRuntimeStatus:
        return self.delivery_store.get_runtime_status()

    def list_delivery_executions(self, limit: int = 20) -> list[XianyuDeliveryExecutionRecord]:
        return self.delivery_store.list_executions(limit=limit)

    async def handle_delivery_candidate_event(self, event: dict[str, Any]) -> None:
        """把聊天推送中识别到的付款/待发货事件交给自动发货运行时处理。"""
        await self.delivery_runtime.process_event(event, executor=self)

    async def send_chat_and_ship(
        self,
        *,
        order_id: str,
        item_id: str,
        buyer_id: str,
        delivery_text: str,
    ) -> dict[str, Any]:
        """自动发货执行器：优先发送聊天发货文本，虚拟发货接口后续可在这里扩展。"""
        cid = self._find_cached_delivery_cid(item_id=item_id, buyer_id=buyer_id)
        if not cid:
            with contextlib.suppress(Exception):
                page = await self.list_chat_conversations(offset=0, limit=40)
                for session in page.conversations:
                    if session.item_id == str(item_id) and session.peer_user_id == str(buyer_id):
                        cid = session.cid
                        break

        sent_message_id = ""
        if cid and str(delivery_text or "").strip():
            result = await self.send_chat_text(cid=cid, text=str(delivery_text).strip())
            sent_message_id = result.message_id
        elif not cid:
            logger.warning("自动发货未找到可发送会话: order_id=%s item_id=%s buyer_id=%s", order_id, item_id, buyer_id)

        return {
            "success": True,
            "order_id": order_id,
            "item_id": item_id,
            "buyer_id": buyer_id,
            "cid": cid,
            "message_id": sent_message_id,
        }

    def _find_cached_delivery_cid(self, *, item_id: str, buyer_id: str) -> str:
        normalized_item_id = str(item_id or "").strip()
        normalized_buyer_id = str(buyer_id or "").strip()
        for cid, cached in self._conversation_item_cache.items():
            if "@" not in str(cid):
                continue
            if (
                str(cached.get("item_id") or "").strip() == normalized_item_id
                and str(cached.get("peer_user_id") or "").strip() == normalized_buyer_id
            ):
                return str(cid)
        return ""

    def _extract_delivery_candidate_event(
        self,
        decoded: dict[str, Any],
        profile: XianyuChatProfile | None = None,
    ) -> dict[str, str] | None:
        """从聊天 sync 推送中提取“买家已付款/待发货”候选事件。"""
        if not isinstance(decoded, dict) or decoded.get("type") != "sync":
            return None

        current_user_id = ""
        if profile:
            current_user_id = str(profile.main_user_id or profile.user_id or "").split("@", 1)[0]

        for item in decoded.get("items") or []:
            item_decoded = item.get("decoded") or {}
            if not isinstance(item_decoded, dict):
                continue

            for obj in item_decoded.get("json_objects") or []:
                payload = obj.get("1") if isinstance(obj, dict) else None
                if not isinstance(payload, dict):
                    continue
                if not self._is_delivery_system_payload(payload):
                    continue

                cid = str(payload.get("2") or "").strip()
                cid_short = cid.split("@", 1)[0] if cid else ""
                meta = payload.get("10") if isinstance(payload.get("10"), dict) else {}
                ext_wrapper = payload.get("3") if isinstance(payload.get("3"), dict) else {}
                extension = ext_wrapper.get("extension") if isinstance(ext_wrapper.get("extension"), dict) else {}
                cached = (
                    self._conversation_item_cache.get(cid)
                    or self._conversation_item_cache.get(cid_short)
                    or {}
                )

                text = str(meta.get("reminderContent") or meta.get("detailNotice") or "").strip()
                raw_sources = [
                    str(item_decoded.get("raw_text") or ""),
                    " ".join(str(url) for url in (item_decoded.get("urls") or [])),
                    str(extension.get("updateKey") or ""),
                    text,
                ]
                order_id = self._extract_delivery_order_id(" ".join(raw_sources))
                item_id = str(extension.get("itemId") or cached.get("item_id") or "").strip()
                sender_id = str(meta.get("senderUserId") or "").split("@", 1)[0].strip()
                buyer_id = sender_id
                if not buyer_id or buyer_id in {"0", "-1"} or (current_user_id and buyer_id == current_user_id):
                    buyer_id = str(cached.get("peer_user_id") or "").strip()

                if order_id and item_id and buyer_id:
                    return {
                        "order_id": order_id,
                        "item_id": item_id,
                        "buyer_id": buyer_id,
                        "text": text,
                    }
        return None

    def _is_delivery_system_payload(self, payload: dict[str, Any]) -> bool:
        flag = self._to_int(payload.get("7"))
        notice_type = self._to_int((((payload.get("6") or {}).get("3") or {}).get("4")))
        return flag == 1 and notice_type == 6

    def _extract_delivery_order_id(self, text: str) -> str:
        source = str(text or "")
        patterns = [
            r"(?:orderId|order_id|tradeId|bizOrderId)=([0-9]{8,})",
            r"trade_paid_done_seller:([0-9]{8,})",
        ]
        for pattern in patterns:
            match = re.search(pattern, source)
            if match:
                return match.group(1)
        return ""
