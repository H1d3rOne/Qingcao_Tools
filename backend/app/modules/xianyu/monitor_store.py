from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.config_bootstrap import write_json_atomic
from app.modules.xianyu.schemas import XianyuMonitorHit, XianyuMonitorTask, XianyuMonitorTaskCreate


class XianyuMonitorStore:
    """闲鱼监控任务本地 JSON 存储"""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list_tasks(self) -> list[XianyuMonitorTask]:
        return self._load()

    def create_task(self, payload: XianyuMonitorTaskCreate) -> XianyuMonitorTask:
        now = int(time.time())
        task = XianyuMonitorTask(
            id=uuid.uuid4().hex,
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        )
        tasks = self._load()
        tasks.append(task)
        self._save(tasks)
        return task

    def update_task(self, task_id: str, updates: dict[str, Any]) -> XianyuMonitorTask | None:
        tasks = self._load()
        for index, task in enumerate(tasks):
            if task.id != task_id:
                continue
            updated = task.model_copy(update={**updates, "updated_at": int(time.time())})
            tasks[index] = updated
            self._save(tasks)
            return updated
        return None

    def delete_task(self, task_id: str) -> bool:
        tasks = self._load()
        remaining = [task for task in tasks if task.id != task_id]
        if len(remaining) == len(tasks):
            return False
        self._save(remaining)
        return True

    def record_run(
        self,
        task_id: str,
        *,
        new_hits: list[dict[str, Any]],
        seen_item_ids: list[str],
        status: str = "ok",
        error: str = "",
    ) -> XianyuMonitorTask | None:
        now = int(time.time())
        payload_hits = [
            XianyuMonitorHit(discovered_at=now, **item)
            for item in new_hits
        ]

        tasks = self._load()
        for index, task in enumerate(tasks):
            if task.id != task_id:
                continue

            dedup: dict[str, XianyuMonitorHit] = {}
            for item in [*reversed(payload_hits), *task.latest_hits]:
                dedup[item.item_id] = item

            updated = task.model_copy(
                update={
                    "updated_at": now,
                    "last_run_at": now,
                    "last_status": status,
                    "last_error": error,
                    "seen_item_ids": seen_item_ids[-500:],
                    "latest_hits": list(dedup.values())[:50],
                }
            )
            tasks[index] = updated
            self._save(tasks)
            return updated
        return None

    def _load(self) -> list[XianyuMonitorTask]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [XianyuMonitorTask.model_validate(item) for item in data]

    def _save(self, tasks: list[XianyuMonitorTask]) -> None:
        write_json_atomic(self.path, [task.model_dump() for task in tasks])
