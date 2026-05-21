"""运行态配置初始化与备份工具。

仓库只提交 ``backend/config.example`` 里的安全模板；真实 Cookie、API Key、设备指纹等
运行态配置统一落到 ``backend/config``，并由 ``.gitignore`` 排除，避免误提交。
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Iterable


BACKEND_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_CONFIG_DIR = BACKEND_ROOT / "config"
DEFAULT_EXAMPLE_CONFIG_DIR = BACKEND_ROOT / "config.example"
LEGACY_APP_CONFIG_DIR = APP_ROOT / "config"

DEFAULT_BACKEND_CONFIG: dict = {
    "app": {
        "name": "青草工具箱 API",
        "version": "1.0.0",
        "debug": False,
        "api_prefix": "/api/v1",
    },
    "server": {"host": "0.0.0.0", "port": 5000},
    "database": {"url": "sqlite+aiosqlite:///./data.db"},
    "redis": {"url": "redis://localhost:6379/0", "enabled": False},
    "cookies": {"douyin": "", "douyin_live": "", "quark": "", "xianyu": ""},
    "download": {"path": "./datas/media", "excel_path": "./datas/excel"},
    "security": {
        "secret_key": "please-change-this-secret-key-in-production",
        "access_token_expire_minutes": 1440,
    },
    "request": {"timeout": 30, "max_retries": 3},
    "log": {
        "path": "./logs",
        "level": "INFO",
        "rotation": "10 MB",
        "retention": "7 days",
    },
}

TEMPLATE_CONFIG_FILES: tuple[str, ...] = (
    "config.yaml",
    "quark_cookies.json",
    "xianyu_ai_config.json",
    "xianyu_ai_sessions.json",
    "xianyu_chat_devices.json",
    "xianyu_cookies.json",
    "xianyu_delivery_rules.json",
    "xianyu_delivery_runtime.json",
    "xianyu_fingerprint.json",
    "xianyu_manage_items.json",
    "xianyu_monitor_tasks.json",
)

RESTORABLE_BACKUP_FILES: tuple[str, ...] = (
    "config.yaml",
    "xianyu_ai_config.json",
    "xianyu_ai_sessions.json",
    "xianyu_chat_devices.json",
    "xianyu_delivery_rules.json",
    "xianyu_delivery_runtime.json",
    "xianyu_manage_items.json",
    "xianyu_monitor_tasks.json",
)


def get_runtime_config_dir() -> Path:
    """返回统一运行态配置目录。"""
    configured = os.getenv("QINGCAO_CONFIG_DIR")
    return Path(configured).expanduser() if configured else DEFAULT_RUNTIME_CONFIG_DIR


def get_example_config_dir() -> Path:
    configured = os.getenv("QINGCAO_CONFIG_EXAMPLE_DIR")
    return Path(configured).expanduser() if configured else DEFAULT_EXAMPLE_CONFIG_DIR


def ensure_runtime_config(
    *,
    runtime_dir: Path | None = None,
    example_dir: Path | None = None,
    legacy_dir: Path | None = None,
) -> Path:
    """确保运行态配置存在，并尽量保护已有本地配置。

    规则：
    1. 真实配置目录默认是 ``backend/config``，也可用 ``QINGCAO_CONFIG_DIR`` 覆盖；
    2. 只在文件缺失时初始化，绝不覆盖用户已有配置；
    3. ``config.yaml`` 缺失时优先迁移旧位置 ``backend/app/config/config.yaml``；
    4. 若同名 ``.bak`` 存在，优先从备份恢复，防止误删后配置消失；
    5. 设置 ``XIANYU_CONFIG_DIR`` / ``QUARK_CONFIG_DIR`` 默认值，让各模块共用同一目录。
    """
    target_dir = Path(runtime_dir or get_runtime_config_dir()).expanduser().resolve()
    source_dir = Path(example_dir or get_example_config_dir()).expanduser().resolve()
    legacy_config_dir = Path(legacy_dir or LEGACY_APP_CONFIG_DIR).expanduser().resolve()

    target_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("QINGCAO_CONFIG_DIR", str(target_dir))
    os.environ.setdefault("XIANYU_CONFIG_DIR", str(target_dir))
    os.environ.setdefault("QUARK_CONFIG_DIR", str(target_dir))

    _restore_missing_from_backups(target_dir, RESTORABLE_BACKUP_FILES)

    main_config = target_dir / "config.yaml"
    legacy_config = legacy_config_dir / "config.yaml"
    if not main_config.exists() and legacy_config.exists():
        shutil.copy2(legacy_config, main_config)

    for filename in TEMPLATE_CONFIG_FILES:
        destination = target_dir / filename
        if destination.exists():
            continue
        template = source_dir / filename
        if template.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(template, destination)

    return target_dir


def backup_runtime_file(path: Path, *, keep_timestamped: bool = False) -> Path | None:
    """为运行态配置文件创建 ``.bak`` 备份。

    默认维护一个稳定的 ``文件名.bak``，便于自动恢复；需要排查历史时可传
    ``keep_timestamped=True`` 额外保留时间戳副本。
    """
    source = Path(path)
    if not source.exists() or not source.is_file():
        return None

    backup_path = source.with_suffix(source.suffix + ".bak")
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, backup_path)

    if keep_timestamped:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        timestamped = source.with_name(f"{source.name}.{timestamp}.bak")
        shutil.copy2(source, timestamped)

    return backup_path


def write_json_atomic(path: Path, payload: object) -> None:
    """原子写入 JSON，并在写入前后维护 ``.bak``。"""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup_runtime_file(destination)
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(destination)
    backup_runtime_file(destination)


def _restore_missing_from_backups(target_dir: Path, filenames: Iterable[str]) -> None:
    for filename in filenames:
        destination = target_dir / filename
        backup_path = destination.with_suffix(destination.suffix + ".bak")
        if not destination.exists() and backup_path.exists():
            shutil.copy2(backup_path, destination)
