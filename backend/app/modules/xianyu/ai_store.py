from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.modules.xianyu.schemas import (
    XianyuChatAiConfig,
    XianyuChatAiProvider,
    XianyuChatAiProviderCreateRequest,
    XianyuChatAiProviderUpdateRequest,
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
        providers_payload = payload.get("providers") or []
        providers = []
        for p in providers_payload:
            if isinstance(p, dict):
                api_key = str(p.get("api_key") or "")
                # 兼容旧格式：model 字段转为 models 列表
                models = p.get("models")
                if not models or not isinstance(models, list):
                    old_model = str(p.get("model") or "")
                    models = [old_model] if old_model else []
                active_model = str(p.get("active_model") or "")
                if not active_model and models:
                    active_model = models[0]
                providers.append(XianyuChatAiProvider(
                    id=str(p.get("id") or ""),
                    name=str(p.get("name") or "未命名"),
                    base_url=str(p.get("base_url") or ""),
                    models=models,
                    active_model=active_model,
                    system_prompt=str(p.get("system_prompt") or ""),
                    api_key_configured=bool(api_key),
                    api_key_masked=self._mask_api_key(api_key),
                    is_active=bool(p.get("is_active", False)),
                ))
        return XianyuChatAiConfig(
            enabled=bool(payload.get("enabled", False)),
            chat_keepalive_interval_seconds=int(payload.get("chat_keepalive_interval_seconds") or 180),
            providers=providers,
            active_provider_id=str(payload.get("active_provider_id") or ""),
        )

    def load_secret_api_key(self, provider_id: str) -> str:
        payload = self._read_json(self.config_path, {})
        providers = payload.get("providers") or []
        for p in providers:
            if isinstance(p, dict) and str(p.get("id")) == provider_id:
                return str(p.get("api_key") or "")
        return ""

    def get_active_provider(self) -> XianyuChatAiProvider | None:
        config = self.load_config()
        if not config.active_provider_id:
            return config.providers[0] if config.providers else None
        for p in config.providers:
            if p.id == config.active_provider_id:
                return p
        return config.providers[0] if config.providers else None

    def create_provider(self, request: XianyuChatAiProviderCreateRequest) -> XianyuChatAiProvider:
        payload = self._read_json(self.config_path, {})
        providers = list(payload.get("providers") or [])
        new_id = str(uuid.uuid4())[:8]
        models = request.models or []
        active_model = request.active_model or (models[0] if models else "")
        new_provider = {
            "id": new_id,
            "name": request.name.strip(),
            "base_url": request.base_url.strip().rstrip("/"),
            "api_key": request.api_key.strip(),
            "models": models,
            "active_model": active_model,
            "system_prompt": request.system_prompt.strip(),
            "is_active": len(providers) == 0,
        }
        providers.append(new_provider)
        if len(providers) == 1:
            payload["active_provider_id"] = new_id
        payload["providers"] = providers
        self._write_json(self.config_path, payload)
        return XianyuChatAiProvider(
            id=new_id,
            name=new_provider["name"],
            base_url=new_provider["base_url"],
            models=models,
            active_model=active_model,
            system_prompt=new_provider["system_prompt"],
            api_key_configured=bool(request.api_key.strip()),
            api_key_masked=self._mask_api_key(request.api_key),
            is_active=new_provider["is_active"],
        )

    def update_provider(self, provider_id: str, request: XianyuChatAiProviderUpdateRequest) -> XianyuChatAiProvider | None:
        payload = self._read_json(self.config_path, {})
        providers = list(payload.get("providers") or [])
        updated = None
        for i, p in enumerate(providers):
            if isinstance(p, dict) and str(p.get("id")) == provider_id:
                if request.name is not None:
                    p["name"] = request.name.strip()
                if request.base_url is not None:
                    p["base_url"] = request.base_url.strip().rstrip("/")
                if request.api_key is not None:
                    p["api_key"] = request.api_key.strip()
                if request.models is not None:
                    p["models"] = request.models
                if request.active_model is not None:
                    p["active_model"] = request.active_model.strip()
                if request.system_prompt is not None:
                    p["system_prompt"] = request.system_prompt.strip()
                providers[i] = p
                updated = p
                break
        if not updated:
            return None
        payload["providers"] = providers
        self._write_json(self.config_path, payload)
        api_key = str(updated.get("api_key") or "")
        models = updated.get("models") or []
        active_model = str(updated.get("active_model") or "")
        if not active_model and models:
            active_model = models[0] if isinstance(models, list) else ""
        return XianyuChatAiProvider(
            id=str(updated.get("id") or ""),
            name=str(updated.get("name") or ""),
            base_url=str(updated.get("base_url") or ""),
            models=models if isinstance(models, list) else [],
            active_model=active_model,
            system_prompt=str(updated.get("system_prompt") or ""),
            api_key_configured=bool(api_key),
            api_key_masked=self._mask_api_key(api_key),
            is_active=bool(updated.get("is_active", False)),
        )

    def delete_provider(self, provider_id: str) -> bool:
        payload = self._read_json(self.config_path, {})
        providers = list(payload.get("providers") or [])
        new_providers = [p for p in providers if isinstance(p, dict) and str(p.get("id")) != provider_id]
        if len(new_providers) == len(providers):
            return False
        payload["providers"] = new_providers
        if str(payload.get("active_provider_id")) == provider_id:
            payload["active_provider_id"] = new_providers[0].get("id") if new_providers else ""
        self._write_json(self.config_path, payload)
        return True

    def set_active_provider(self, provider_id: str) -> bool:
        payload = self._read_json(self.config_path, {})
        providers = list(payload.get("providers") or [])
        found = False
        for p in providers:
            if isinstance(p, dict):
                p["is_active"] = str(p.get("id")) == provider_id
                if p["is_active"]:
                    found = True
        if not found:
            return False
        payload["providers"] = providers
        payload["active_provider_id"] = provider_id
        self._write_json(self.config_path, payload)
        return True

    def set_enabled(self, enabled: bool) -> XianyuChatAiConfig:
        payload = self._read_json(self.config_path, {})
        payload["enabled"] = enabled
        self._write_json(self.config_path, payload)
        return self.load_config()

    def set_chat_keepalive_interval_seconds(self, seconds: int) -> XianyuChatAiConfig:
        payload = self._read_json(self.config_path, {})
        payload["chat_keepalive_interval_seconds"] = max(30, min(int(seconds), 3600))
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

    def has_any_enabled_session(self) -> bool:
        payload = self._read_json(self.sessions_path, {"sessions": {}})
        sessions = dict(payload.get("sessions") or {})
        return any(bool(enabled) for enabled in sessions.values())

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
