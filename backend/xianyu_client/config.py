from __future__ import annotations

import os
from pathlib import Path


def get_config_dir() -> Path:
    config_dir = os.getenv("XIANYU_CONFIG_DIR")
    if config_dir:
        return Path(config_dir)
    return Path.cwd() / "config"
