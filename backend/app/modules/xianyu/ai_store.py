from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
        api_key = str(payload.get("api_key") or "")
        return XianyuChatAiConfig(
            enabled=bool(payload.get("enabled", False)),
            base_url=str(payload.get("base_url") or "https://api.openai.com/v1"),
            model=str(payload.get("model") or "gpt-4.1-mini"),
            system_prompt=str(payload.get("system_prompt") or "你是闲鱼客服助手，回复要简洁、礼貌、像真人卖家。"),
            temperature=float(payload.get("temperature", 0.3)),
            api_key_configured=bool(api_key),
            api_key_masked=self._mask_api_key(api_key),
        )

    def load_secret_api_key(self) -> str:
        payload = self._read_json(self.config_path, {})
        return str(payload.get("api_key") or "")

    def save_config(self, request: XianyuChatAiConfigUpdateRequest) -> XianyuChatAiConfig:
        current = self._read_json(self.config_path, {})
        next_api_key = request.api_key.strip() or str(current.get("api_key") or "")
        payload = {
            "enabled": request.enabled,
            "base_url": request.base_url.strip().rstrip("/"),
            "api_key": next_api_key,
            "model": request.model.strip(),
            "system_prompt": request.system_prompt.strip(),
            "temperature": request.temperature,
        }
        self._write_json(self.config_path, payload)
        return self.load_config()

    def get_session_enabled(self, cid: str) -> bool:
        payload = self._read_json(self.sessions_path, {"sessions": {}})
        return bool((payload.get("sessions") or {}).get(cid, False))

    def set_session_enabled(self, cid: str, enabled: bool) -> XianyuChatAiSessionState:
        payload = self._read_json(self.sessions_path, {"sessions": {}})
        sessions = dict(payload.get("sessions") or {})
        sessions[cid] = enabled
        self._write_json(self.sessions_path, {"sessions": sessions})
        return XianyuChatAiSessionState(cid=cid, enabled=enabled)

    def list_session_states(self, cids: list[str]) -> list[XianyuChatAiSessionState]:
        payload = self._read_json(self.sessions_path, {"sessions": {}})
        sessions = dict(payload.get("sessions") or {})
        return [XianyuChatAiSessionState(cid=cid, enabled=bool(sessions.get(cid, False))) for cid in cids]

    def _read_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return dict(default)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return dict(default)

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _mask_api_key(self, api_key: str) -> str:
        if not api_key:
            return ""
        if len(api_key) <= 8:
            return "*" * len(api_key)
        return f"{api_key[:3]}****{api_key[-4:]}"
