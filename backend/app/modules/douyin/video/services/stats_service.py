"""
使用统计服务
"""
import os
import json
import time
from pathlib import Path
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.work import Work
from app.core.config import settings


STATS_FILE = Path(__file__).parent.parent.parent.parent.parent / "datas" / "stats.json"


class StatsTracker:
    """API 调用统计追踪器（单例）"""

    def __init__(self):
        self._data = {"success": 0, "fail": 0}
        self._load()

    def _load(self):
        if STATS_FILE.exists():
            try:
                with open(STATS_FILE, "r") as f:
                    self._data = json.load(f)
            except Exception:
                pass

    def _save(self):
        STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATS_FILE, "w") as f:
            json.dump(self._data, f)

    def record_success(self):
        self._data["success"] = self._data.get("success", 0) + 1
        self._save()

    def record_fail(self):
        self._data["fail"] = self._data.get("fail", 0) + 1
        self._save()

    @property
    def success_count(self) -> int:
        return self._data.get("success", 0)

    @property
    def fail_count(self) -> int:
        return self._data.get("fail", 0)

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        if total == 0:
            return 100.0
        return round(self.success_count / total * 100, 1)


stats_tracker = StatsTracker()


class StatsService:
    """统计服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stats(self) -> dict:
        parsed_count = await self._get_parsed_count()
        downloaded_count = self._get_downloaded_count()
        success_rate = stats_tracker.success_rate

        return {
            "parsed_count": parsed_count,
            "downloaded_count": downloaded_count,
            "success_rate": success_rate,
        }

    async def _get_parsed_count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(Work))
        return result.scalar() or 0

    def _get_downloaded_count(self) -> int:
        media_dir = Path(settings.DOWNLOAD_PATH)
        if not media_dir.exists():
            media_dir = Path(__file__).parent.parent.parent.parent.parent / "datas" / "media_datas"
        if not media_dir.exists():
            return 0

        count = 0
        for root, dirs, files in os.walk(media_dir):
            for f in files:
                if f.endswith(('.mp4', '.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    count += 1
        return count
