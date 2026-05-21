import json
import time
import uuid
from pathlib import Path

from app.core.config_bootstrap import write_json_atomic
from app.modules.xianyu.schemas import (
    XianyuDeliveryExecutionRecord,
    XianyuDeliveryRule,
    XianyuDeliveryRuleCreateRequest,
    XianyuDeliveryRuleUpdateRequest,
    XianyuDeliveryRuntimeStatus,
)


class XianyuDeliveryStore:
    def __init__(self, rules_path: Path, runtime_path: Path):
        self.rules_path = Path(rules_path)
        self.runtime_path = Path(runtime_path)
        self.rules_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_rules(self) -> list[dict]:
        if not self.rules_path.exists():
            return []
        raw = self.rules_path.read_text(encoding="utf-8").strip()
        return json.loads(raw or "[]")

    def _save_rules(self, rules: list[dict]) -> None:
        write_json_atomic(self.rules_path, rules)

    def _default_runtime_state(self) -> dict:
        return {
            "running": False,
            "last_event_at": 0,
            "last_success_at": 0,
            "last_failure_at": 0,
            "last_error": "",
            "enabled_rule_count": 0,
            "recent_success_count": 0,
            "recent_failure_count": 0,
            "executions": [],
        }

    def _load_runtime_state(self) -> dict:
        if not self.runtime_path.exists():
            return self._default_runtime_state()
        raw = self.runtime_path.read_text(encoding="utf-8").strip()
        data = json.loads(raw or "{}")
        state = self._default_runtime_state()
        state.update(data or {})
        state["executions"] = list(state.get("executions") or [])
        return state

    def _save_runtime_state(self, state: dict) -> None:
        write_json_atomic(self.runtime_path, state)

    def _ensure_runtime_file(self) -> None:
        if not self.runtime_path.exists():
            self._save_runtime_state(self._default_runtime_state())

    def _refresh_enabled_rule_count(self, state: dict | None = None) -> dict:
        current = state or self._load_runtime_state()
        current["enabled_rule_count"] = sum(
            1 for rule in self._load_rules() if bool(rule.get("enabled"))
        )
        return current

    def list_rules(self) -> list[XianyuDeliveryRule]:
        return [XianyuDeliveryRule(**rule) for rule in self._load_rules()]

    def create_rule(self, request: XianyuDeliveryRuleCreateRequest) -> XianyuDeliveryRule:
        now = int(time.time())
        rule = XianyuDeliveryRule(
            id=uuid.uuid4().hex,
            created_at=now,
            updated_at=now,
            **request.model_dump(),
        )
        rules = self._load_rules()
        rules.append(rule.model_dump())
        self._save_rules(rules)
        state = self._refresh_enabled_rule_count()
        self._save_runtime_state(state)
        return rule

    def toggle_rule(self, rule_id: str) -> XianyuDeliveryRule | None:
        normalized = str(rule_id or "").strip()
        if not normalized:
            return None
        rules = self._load_rules()
        now = int(time.time())
        for rule in rules:
            if str(rule.get("id") or "").strip() != normalized:
                continue
            rule["enabled"] = not bool(rule.get("enabled"))
            rule["updated_at"] = now
            self._save_rules(rules)
            state = self._refresh_enabled_rule_count()
            self._save_runtime_state(state)
            return XianyuDeliveryRule(**rule)
        return None

    def update_rule(self, rule_id: str, payload: dict) -> XianyuDeliveryRule | None:
        normalized = str(rule_id or "").strip()
        if not normalized:
            return None
        rules = self._load_rules()
        now = int(time.time())
        for rule in rules:
            if str(rule.get("id") or "").strip() != normalized:
                continue
            for key, value in (payload or {}).items():
                if key in {"id", "created_at"}:
                    continue
                rule[key] = value
            rule["updated_at"] = now
            self._save_rules(rules)
            state = self._refresh_enabled_rule_count()
            self._save_runtime_state(state)
            return XianyuDeliveryRule(**rule)
        return None

    def delete_rule(self, rule_id: str) -> bool:
        normalized = str(rule_id or "").strip()
        if not normalized:
            return False
        rules = self._load_rules()
        filtered = [rule for rule in rules if str(rule.get("id") or "").strip() != normalized]
        if len(filtered) == len(rules):
            return False
        self._save_rules(filtered)
        state = self._refresh_enabled_rule_count()
        self._save_runtime_state(state)
        return True

    def list_executions(self, limit: int = 20) -> list[XianyuDeliveryExecutionRecord]:
        state = self._load_runtime_state()
        executions = list(state.get("executions") or [])[: max(int(limit or 20), 1)]
        return [XianyuDeliveryExecutionRecord(**item) for item in executions]

    def mark_runtime_running(self, running: bool) -> XianyuDeliveryRuntimeStatus:
        state = self._refresh_enabled_rule_count()
        state["running"] = bool(running)
        self._save_runtime_state(state)
        data = {key: value for key, value in state.items() if key != "executions"}
        return XianyuDeliveryRuntimeStatus(**data)

    def mark_runtime_event(self) -> XianyuDeliveryRuntimeStatus:
        state = self._refresh_enabled_rule_count()
        state["last_event_at"] = int(time.time())
        self._save_runtime_state(state)
        data = {key: value for key, value in state.items() if key != "executions"}
        return XianyuDeliveryRuntimeStatus(**data)

    def record_execution(
        self,
        *,
        rule_id: str,
        rule_name: str,
        order_id: str,
        item_id: str,
        buyer_id: str,
        status: str,
        message: str,
    ) -> XianyuDeliveryExecutionRecord:
        now = int(time.time())
        record = XianyuDeliveryExecutionRecord(
            id=uuid.uuid4().hex,
            rule_id=rule_id,
            rule_name=rule_name,
            order_id=order_id,
            item_id=item_id,
            buyer_id=buyer_id,
            status=status,
            message=message,
            created_at=now,
        )
        state = self._load_runtime_state()
        executions = list(state.get("executions") or [])
        executions.insert(0, record.model_dump())
        state["executions"] = executions[:100]
        if status == "success":
            state["last_success_at"] = now
            state["recent_success_count"] = int(state.get("recent_success_count") or 0) + 1
        elif status == "failed":
            state["last_failure_at"] = now
            state["last_error"] = message
            state["recent_failure_count"] = int(state.get("recent_failure_count") or 0) + 1
        self._save_runtime_state(self._refresh_enabled_rule_count(state))
        return record

    def get_runtime_status(self) -> XianyuDeliveryRuntimeStatus:
        state = self._refresh_enabled_rule_count()
        self._save_runtime_state(state)
        data = {key: value for key, value in state.items() if key != "executions"}
        return XianyuDeliveryRuntimeStatus(**data)
