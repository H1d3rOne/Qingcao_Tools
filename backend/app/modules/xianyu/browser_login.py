from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
import contextlib
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
    cleanup: Callable[[], Any] | None = None
    monitor_task: asyncio.Task | None = None


class XianyuBrowserLoginManager:
    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self._active_session_id: str | None = None
        self._sessions: dict[str, XianyuBrowserLoginSession] = {}

    def create_session(
        self,
        *,
        qrcode_image: str,
        cleanup=None,
        expires_in: int = 300,
    ) -> XianyuBrowserLoginSession:
        if self._active_session_id:
            self._close_session(self._active_session_id, remove=True)
        session = XianyuBrowserLoginSession(
            session_id=uuid.uuid4().hex[:12],
            qrcode_image=qrcode_image,
            expires_at=int(time.time()) + int(expires_in),
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

    def update_session(
        self,
        session_id: str,
        *,
        status: str | None = None,
        message: str | None = None,
        qrcode_image: str | None = None,
        login_token: str | None = None,
    ) -> XianyuBrowserLoginSession:
        session = self._require_session(session_id)
        if status is not None:
            session.status = status
        if message is not None:
            session.message = message
        if qrcode_image is not None:
            session.qrcode_image = qrcode_image
        if login_token is not None:
            session.login_token = login_token
        return session

    def bind_runtime(
        self,
        session_id: str,
        *,
        cleanup: Callable[[], Any] | None = None,
        monitor_task: asyncio.Task | None = None,
    ) -> XianyuBrowserLoginSession:
        session = self._require_session(session_id)
        if cleanup is not None:
            session.cleanup = cleanup
        if monitor_task is not None:
            session.monitor_task = monitor_task
        return session

    def mark_success(self, session_id: str, *, cookie_string: str) -> dict[str, Any]:
        session = self._require_session(session_id)
        save_xianyu_cookie_string(cookie_string, config_dir=self.config_dir, source='browser_qrcode')
        session.status = 'success'
        session.message = '登录成功'
        session.login_token = cookie_string
        if self._active_session_id == session_id:
            self._active_session_id = None
        return {
            'success': True,
            'message': session.message,
            'status': session.status,
            'is_logged_in': True,
            'login_token': cookie_string,
        }

    def cancel_session(self, session_id: str, message: str = '已取消扫码登录') -> dict[str, Any]:
        session = self._require_session(session_id)
        session.status = 'cancelled'
        session.message = message
        if session.monitor_task and not session.monitor_task.done():
            session.monitor_task.cancel()
        if self._active_session_id == session_id:
            self._active_session_id = None
        return {'success': True, 'message': session.message}

    def _require_session(self, session_id: str) -> XianyuBrowserLoginSession:
        session = self.get_session(session_id)
        if not session:
            raise ValueError('扫码会话不存在或已失效')
        return session

    def _close_session(self, session_id: str, *, remove: bool) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        if session.monitor_task and not session.monitor_task.done():
            session.monitor_task.cancel()
        elif session.cleanup:
            with contextlib.suppress(Exception):
                result = session.cleanup()
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
        if remove:
            self._sessions.pop(session_id, None)
        if self._active_session_id == session_id:
            self._active_session_id = None
