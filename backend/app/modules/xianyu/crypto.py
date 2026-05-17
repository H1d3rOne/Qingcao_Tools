"""闲鱼聊天消息解密工具

通过 PyExecJS 调用 `scripts/goofish_js.js`（来源：XianYuApis 项目逆向产物，
2025-04 快照）。JS 内包含 MsgPack 解包逻辑，`decrypt(base64_str)` 会返回可被
`json.loads` 的 JSON 字符串。
"""
from __future__ import annotations

import logging
import subprocess
from functools import partial
from pathlib import Path
from threading import Lock

subprocess.Popen = partial(subprocess.Popen, encoding="utf-8")
import execjs  # noqa: E402

_log = logging.getLogger(__name__)

_JS_PATH = Path(__file__).parent / "scripts" / "goofish_js.js"
_xianyu_js = None
_compile_lock = Lock()
_compile_attempted = False


def _get_runtime():
    global _xianyu_js, _compile_attempted
    if _xianyu_js is not None or _compile_attempted:
        return _xianyu_js
    with _compile_lock:
        if _xianyu_js is not None or _compile_attempted:
            return _xianyu_js
        _compile_attempted = True
        try:
            source = _JS_PATH.read_text(encoding="utf-8")
            _xianyu_js = execjs.compile(source)
        except Exception as exc:
            _log.warning("goofish JS 加载失败，闲鱼消息解密将不可用: %s", exc)
            _xianyu_js = None
    return _xianyu_js


def decrypt(data: str) -> str | None:
    """解密闲鱼 syncPushPackage 中 base64 编码的 MsgPack 数据，成功返回 JSON 字符串。"""
    if not data:
        return None
    runtime = _get_runtime()
    if runtime is None:
        return None
    try:
        return runtime.call("decrypt", data)
    except Exception as exc:
        _log.warning("闲鱼消息解密失败: %s", exc)
        return None


def generate_mid() -> str | None:
    runtime = _get_runtime()
    if runtime is None:
        return None
    try:
        return runtime.call("generate_mid")
    except Exception as exc:
        _log.warning("generate_mid 调用失败: %s", exc)
        return None


def generate_uuid() -> str | None:
    runtime = _get_runtime()
    if runtime is None:
        return None
    try:
        return runtime.call("generate_uuid")
    except Exception as exc:
        _log.warning("generate_uuid 调用失败: %s", exc)
        return None


def generate_device_id(user_id: str) -> str | None:
    runtime = _get_runtime()
    if runtime is None:
        return None
    try:
        return runtime.call("generate_device_id", user_id)
    except Exception as exc:
        _log.warning("generate_device_id 调用失败: %s", exc)
        return None


def generate_sign(t, token: str, data: str) -> str | None:
    runtime = _get_runtime()
    if runtime is None:
        return None
    try:
        return runtime.call("generate_sign", t, token, data)
    except Exception as exc:
        _log.warning("generate_sign 调用失败: %s", exc)
        return None
