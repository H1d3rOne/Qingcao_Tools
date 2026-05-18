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
from app.modules.xianyu.ai_store import XianyuChatAiStore
from app.modules.xianyu.delivery_runtime import XianyuDeliveryRuntime
from app.modules.xianyu.delivery_store import XianyuDeliveryStore
from app.modules.xianyu.item_store import XianyuItemStore
from app.modules.xianyu.monitor_store import XianyuMonitorStore
from app.modules.xianyu.schemas import (
    XianyuChatAiConfig,
    XianyuChatAiConfigUpdateRequest,
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

    async def send_rpc(
        self,
        lwp: str,
        body: Any = None,
        headers: Optional[Dict[str, Any]] = None,
        timeout: float = 15.0,
    ) -> Dict[str, Any]:
        if not self._ws:
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
    chat_login_user_api_name = "mtop.taobao.idlemessage.pc.loginuser.get"
    chat_login_user_api_url = "https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.loginuser.get/1.0/"
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
        self._monitor_store_path = Path.cwd() / "config" / "xianyu_monitor_tasks.json"
        self._xianyu_cookie_path = Path.cwd() / "config" / "xianyu_cookies.json"
        self._chat_ai_config_path = Path.cwd() / "config" / "xianyu_ai_config.json"
        self._chat_ai_sessions_path = Path.cwd() / "config" / "xianyu_ai_sessions.json"
        self._item_store_path = Path.cwd() / "config" / "xianyu_manage_items.json"
        self._delivery_rules_path = Path.cwd() / "config" / "xianyu_delivery_rules.json"
        self._delivery_runtime_path = Path.cwd() / "config" / "xianyu_delivery_runtime.json"
        self._monitor_store: XianyuMonitorStore | None = None
        self._chat_ai_store: XianyuChatAiStore | None = None
        self._item_store: XianyuItemStore | None = None
        self._delivery_store: XianyuDeliveryStore | None = None
        self._delivery_runtime: XianyuDeliveryRuntime | None = None
        self._delivery_runtime_running_state: bool = False
        self._monitor_runner_task: asyncio.Task | None = None
        self._auth_login: XianyuAPILogin | None = None
        self._current_qr_payload: dict[str, str] | None = None
        self._processed_ai_message_keys = deque(maxlen=1000)
        self._processed_ai_message_set: set[str] = set()

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

    def _sync_chat_ai_listener_state(self) -> None:
        """Listener state sync hook (no-op: chat AI listener wiring not yet ported)."""
        pass

    def get_chat_ai_config(self) -> XianyuChatAiConfig:
        return self.chat_ai_store.load_config()

    def update_chat_ai_config(self, request: XianyuChatAiConfigUpdateRequest) -> XianyuChatAiConfig:
        return self.chat_ai_store.save_config(request)

    def _load_secret_chat_ai_api_key(self) -> str:
        return self.chat_ai_store.load_secret_api_key().strip()


    def list_chat_ai_session_states(self, cids: list[str]) -> list[Any]:
        return self.chat_ai_store.list_session_states(cids)

    def set_chat_ai_session_state(self, cid: str, enabled: bool):
        return self.chat_ai_store.set_session_enabled(cid, enabled)

    async def test_chat_ai_reply(self, text: str, cid: str = "") -> str:
        config = self.get_chat_ai_config()
        messages = self._build_chat_ai_messages(config=config, text=text, cid=cid)
        return await self._request_chat_ai_reply(config=config, messages=messages)

    def _build_qrcode_data_url(self, content: str) -> str | None:
        try:
            image = qrcode.make(content, image_factory=qrcode.image.svg.SvgImage)
            buffer = io.BytesIO()
            image.save(buffer)
            encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return f"data:image/svg+xml;base64,{encoded}"
        except Exception:
            return None

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
        """诊断闲鱼聊天链路状态"""
        cookie_configured = bool(self._get_xianyu_cookie_value())
        if not cookie_configured:
            return XianyuChatHealthStatus(
                ok=False,
                status="cookie_missing",
                message="未配置闲鱼 Cookie，请先登录后更新 Cookie。",
                shared_ws_connected=False,
                cookie_configured=False,
            )

        try:
            chat_client = await self.open_chat_ws_client()
            connected = bool(chat_client and getattr(chat_client, "_ws", None) is not None)
            return XianyuChatHealthStatus(
                ok=connected,
                status="ok" if connected else "error",
                message="闲鱼聊天链路正常。" if connected else "聊天 WebSocket 未连接。",
                shared_ws_connected=connected,
                cookie_configured=True,
            )
        except Exception as exc:
            error_text = str(exc)
            status = "error"
            captcha_url = ""
            lowered = error_text.lower()
            if "captcha" in lowered or "风控" in error_text or "verify" in lowered:
                status = "risk_blocked"
            elif "auth" in lowered or "登录" in error_text or "token" in lowered:
                status = "auth_invalid"
            return XianyuChatHealthStatus(
                ok=False,
                status=status,
                message=f"聊天链路诊断失败：{error_text}",
                captcha_url=captcha_url,
                shared_ws_connected=False,
                cookie_configured=True,
            )

    async def list_chat_conversations(self, offset: int = 0, limit: int = 20) -> XianyuChatConversationPage:
        """获取聊天会话列表"""
        chat_client = await self.open_chat_ws_client()
        try:
            response = await chat_client.send_rpc("/r/Conversation/listNewest", [offset, limit])
            self._ensure_chat_rpc_success(response, "获取闲鱼聊天会话失败")
            raw_items = [item for item in (response.get("body") or []) if isinstance(item, dict)]
            peer_info_cache: Dict[str, Dict[str, Any]] = {}
            if raw_items:
                peer_ids = set()
                for item in raw_items:
                    single = item.get("singleChatUserConversation") or {}
                    conversation = single.get("singleChatConversation") or {}
                    ext = conversation.get("extension") or {}
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
        finally:
            await chat_client.close()

    async def list_chat_messages(
        self,
        cid: str,
        cursor: str | None = None,
        limit: int = 20,
        direction: str = "prev",
    ) -> XianyuChatMessagePage:
        """获取聊天消息列表"""
        chat_client = await self.open_chat_ws_client()
        try:
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
        finally:
            await chat_client.close()

    async def send_chat_text(self, cid: str, text: str) -> XianyuChatSendResult:
        """发送闲鱼聊天文本消息"""
        summary = text.strip()
        if not summary:
            raise ValueError("请输入要发送的消息内容")

        chat_client = await self.open_chat_ws_client()
        try:
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
        finally:
            await chat_client.close()

    async def clear_chat_red_point(self, cids: List[str]) -> XianyuChatClearResult:
        """清理聊天会话红点"""
        valid_cids = [cid for cid in cids if cid]
        if not valid_cids:
            return XianyuChatClearResult(success_count=0)

        chat_client = await self.open_chat_ws_client()
        try:
            response = await chat_client.send_rpc("/r/Conversation/clearRedPoint", [valid_cids])
            try:
                self._ensure_chat_rpc_success(response, "清理闲鱼聊天红点失败")
            except ValueError as exc:
                message = str(exc).strip()
                if message in {"system is error", "闲鱼走神了，您稍后再试～"}:
                    return XianyuChatClearResult(success_count=0)
                raise
            return XianyuChatClearResult(success_count=len(valid_cids))
        finally:
            await chat_client.close()

    async def send_chat_image(self, cid: str, image_url: str, width: int = 0, height: int = 0) -> XianyuChatSendResult:
        """发送闲鱼聊天图片消息，参照 XianYuApis 的 send_image，含 fallback 重试"""
        chat_client = await self.open_chat_ws_client()
        try:
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
        finally:
            await chat_client.close()

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
        chat_client = await self.open_chat_ws_client()
        try:
            response = await chat_client.send_rpc("/r/MessageManager/recallMessage", [message_id])
            return response.get("code") == 200
        finally:
            await chat_client.close()

    async def mark_chat_read(self, cid: str) -> bool:
        """标记闲鱼聊天消息已读，参照 XianYuApis 的 send_message_read"""
        chat_client = await self.open_chat_ws_client()
        try:
            response = await chat_client.send_rpc("/r/MessageStatus/read", [cid])
            return response.get("code") == 200
        finally:
            await chat_client.close()

    async def create_chat_session(self, peer_user_id: str, item_id: str = "") -> dict[str, Any]:
        """创建单聊会话，参照 XianYuApis 的 create_chat"""
        chat_client = await self.open_chat_ws_client()
        try:
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
        finally:
            await chat_client.close()

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
        config: XianyuChatAiConfig,
        messages: list[dict[str, str]],
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> str:
        api_key = self._load_secret_chat_ai_api_key()
        if not api_key:
            raise ValueError("AI API Key 未配置")

        base_url = config.base_url.rstrip("/")
        payload = {
            "model": config.model,
            "temperature": config.temperature,
            "messages": messages,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0, transport=transport) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            )
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        if not choices:
            raise ValueError("AI 接口未返回可用回复")

        message = choices[0].get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise ValueError("AI 接口返回了空回复")
        return content

    def _extract_ai_candidate(self, item: dict[str, Any]) -> dict[str, str] | None:
        decoded = item.get("decoded") or {}
        if item.get("biz_type") != 40000:
            return None

        for obj in decoded.get("json_objects") or []:
            payload = obj.get("1") or {}
            meta = payload.get("10") or {}
            cid = str(payload.get("2") or "").split("@")[0].strip()
            sender_uid = str(meta.get("senderUserId") or "").strip()
            text = str(meta.get("reminderContent") or "").strip()
            if cid and sender_uid and text:
                raw_text = str(decoded.get("raw_text") or "")
                key = hashlib.sha1(raw_text.encode("utf-8", errors="ignore")).hexdigest()
                return {"cid": cid, "sender_uid": sender_uid, "text": text, "message_key": key}
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

    def _build_chat_ai_messages(self, *, config: XianyuChatAiConfig, text: str, cid: str = "") -> list[dict[str, str]]:
        content = text if not cid else f"会话 CID：{cid}\n买家消息：{text}"
        return [
            {"role": "system", "content": config.system_prompt},
            {"role": "user", "content": content},
        ]

    async def maybe_auto_reply_from_decoded_push(self, profile: XianyuChatProfile, decoded: dict[str, Any]) -> str | None:
        if decoded.get("type") != "sync":
            return None

        config = self.get_chat_ai_config()
        if not config.enabled:
            return None

        current_user_id = profile.main_user_id or profile.user_id
        for item in decoded.get("items") or []:
            candidate = self._extract_ai_candidate(item)
            if not candidate:
                continue
            if candidate["sender_uid"] == current_user_id:
                continue
            if not self.chat_ai_store.get_session_enabled(candidate["cid"]):
                continue
            if not self._remember_ai_message_key(candidate["message_key"]):
                continue

            messages = self._build_chat_ai_messages(config=config, text=candidate["text"], cid=candidate["cid"])
            reply = await self._request_chat_ai_reply(config=config, messages=messages)
            await self.send_chat_text(cid=candidate["cid"], text=reply)
            return reply

        return None

    def _decode_message_data(self, encoded: str) -> Dict[str, Any]:
        """解码推送消息的 data 字段，参照 XianYuApis 的 decode_message_data"""
        try:
            decoded = base64.b64decode(encoded)
            text = decoded.decode("utf-8", errors="replace")
        except Exception:
            return {"raw_text": encoded}

        result: Dict[str, Any] = {
            "raw_text": text,
            "json_objects": [],
            "user_ids": re.findall(r"(\d+)@goofish", text),
            "urls": [],
            "nickname": "",
            "reminder_content": "",
            "sender_user_id": "",
        }
        brace_count = 0
        start = -1
        for i, char in enumerate(text):
            if char == "{":
                if brace_count == 0:
                    start = i
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0 and start >= 0:
                    try:
                        obj = json.loads(text[start : i + 1])
                        result["json_objects"].append(obj)
                        if "reminderTitle" in obj:
                            result["nickname"] = obj["reminderTitle"]
                        if "reminderContent" in obj:
                            result["reminder_content"] = obj["reminderContent"]
                        if "senderUserId" in obj:
                            result["sender_user_id"] = obj["senderUserId"]
                    except Exception:
                        pass
                    start = -1
        url_match = re.search(r"(fleamarket://[^\s\x00]+?)(?=\s|senderUserId|$)", text)
        if url_match:
            result["urls"].append(url_match.group(1))
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
        chat_client = await self.open_chat_ws_client()
        try:
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
        finally:
            await chat_client.close()

    async def open_chat_ws_client(self) -> XianyuChatWsClient:
        """打开闲鱼聊天 WebSocket 客户端，参照 XianYuApis 先刷新 token 再连接"""
        cookie = self._require_xianyu_cookie()
        async with self._create_http_client(cookie) as client:
            await self._refresh_login_state(client)
            bootstrap = await self._build_chat_bootstrap(client, include_token=True)

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
            await chat_client.connect(cookie=cookie)
        except ValueError as exc:
            message = str(exc).strip()
            if message in {"token is not found", "FAIL_SYS_USER_VALIDATE", "FAIL_SYS_SESSION_EXPIRED"}:
                raise ValueError("闲鱼聊天鉴权失败，请重新登录闲鱼后更新设置页中的 Cookie") from exc
            raise
        return chat_client

    async def _execute_api(
        self,
        client: httpx.AsyncClient,
        api_name: str,
        api_url: str,
        payload: Dict,
        extra_params: Optional[Dict[str, str]] = None,
    ) -> Dict:
        """执行通用闲鱼接口请求，参照 xianyu-cli 的 Cookie 冻结 + index API 刷新策略"""
        response_data = await self._perform_api_request(
            client,
            api_name=api_name,
            api_url=api_url,
            payload=payload,
            extra_params=extra_params,
        )

        if self._is_token_expired(response_data):
            self._log.warning("API %s token 过期，直接重试", api_name)
            response_data = await self._perform_api_request(
                client,
                api_name=api_name,
                api_url=api_url,
                payload=payload,
                extra_params=extra_params,
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
        """构建闲鱼聊天初始化上下文，参照 XianYuApis 先获取 token 再获取用户 ID"""
        profile = XianyuChatProfile(
            user_id="",
            main_user_id="",
            domain=self.chat_domain,
            display_name="",
            avatar="",
        )

        bootstrap: Dict[str, Any] = {"profile": profile}
        if not include_token:
            return bootstrap

        device_id = self._build_chat_device_id("")
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
                    "spm_pre": "a21ybx.home.sidebar.2.4c053da6oKH21u",
                    "log_id": "4c053da6oKH21u",
                },
            )
        except ValueError as exc:
            message = str(exc).strip()
            if "RGV587_ERROR" in message:
                raise ValueError(
                    "闲鱼聊天接口被风控拦截，请尝试在浏览器中访问闲鱼网站完成验证后重新更新 Cookie"
                ) from exc
            if "FAIL_SYS_SESSION_EXPIRED" in message:
                raise ValueError("闲鱼登录已过期，请重新登录闲鱼后更新设置页中的 Cookie") from exc
            raise
        access_token = str(token_payload.get("data", {}).get("accessToken") or "")
        if not access_token:
            raise ValueError("闲鱼聊天 token 获取失败，请重新登录闲鱼后更新设置页中的 Cookie")

        bootstrap["device_id"] = device_id
        bootstrap["access_token"] = access_token

        try:
            user_payload = await self._execute_api(
                client,
                api_name=self.chat_login_user_api_name,
                api_url=self.chat_login_user_api_url,
                payload={},
            )
            user_data = user_payload.get("data", {})
            profile.user_id = str(user_data.get("userId") or "")
            profile.main_user_id = str(user_data.get("mainUserId") or user_data.get("userId") or "")
        except Exception:
            pass

        return bootstrap

    async def get_peer_user_info(self, user_id: str) -> Dict[str, Any]:
        cookie = self._require_xianyu_cookie()
        async with self._create_http_client(cookie) as client:
            payload = {"self": False, "userId": user_id}
            result = await self._execute_api(
                client,
                api_name=self.page_head_api_name,
                api_url=self.page_head_api_url,
                payload=payload,
            )
            return result.get("data") or {}

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

        peer_info = (peer_info_cache or {}).get(peer_user_id) or {} if peer_user_id else {}
        _base = (peer_info.get("module") or {}).get("base") or {} if peer_info.get("module") else {}
        peer_display_name = (
            str(_base.get("displayName") or "")
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
        if _base:
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

        return XianyuChatConversation(
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

    def _build_chat_device_id(self, user_id: str) -> str:
        normalized = str(user_id or "0").strip() or "0"
        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        parts = []
        for i in range(36):
            if i in (8, 13, 18, 23):
                parts.append("-")
            elif i == 14:
                parts.append("4")
            elif i == 19:
                parts.append(chars[3 & (ord(chars[random.randint(0, len(chars) - 1)]) & 0xFF) | 8])
            else:
                parts.append(chars[random.randint(0, len(chars) - 1)])
        return "".join(parts) + "-" + normalized

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
        """同步运行时 Cookie，仅更新 _m_h5_tk/_m_h5_tk_enc 到持久存储"""
        current_cookie = self._parse_cookie_string(self._get_xianyu_cookie_value())
        refreshed = False
        for key in ("_m_h5_tk", "_m_h5_tk_enc", "mtop_partitioned_detect"):
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
            return str(ret[0])
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
