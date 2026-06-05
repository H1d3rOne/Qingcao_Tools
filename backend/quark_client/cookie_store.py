"""
Quark cookie storage helpers.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .config import get_config_dir

QUARK_COOKIE_FILE_NAME = "quark_cookies.json"
LEGACY_COOKIE_FILE_NAME = "cookies.json"


def get_quark_cookie_file(config_dir: Optional[Path] = None) -> Path:
    directory = Path(config_dir or get_config_dir())
    directory.mkdir(parents=True, exist_ok=True)
    return directory / QUARK_COOKIE_FILE_NAME


def get_legacy_cookie_file(config_dir: Optional[Path] = None) -> Path:
    directory = Path(config_dir or get_config_dir())
    return directory / LEGACY_COOKIE_FILE_NAME


def cookie_string_to_dict(cookie_string: str) -> Dict[str, str]:
    cookie_dict: Dict[str, str] = {}
    for pair in (cookie_string or "").split(";"):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        name, value = pair.split("=", 1)
        cookie_dict[name.strip()] = value.strip()
    return cookie_dict


def cookie_mapping_to_string(cookies: Mapping[str, str]) -> str:
    return "; ".join(f"{name}={value}" for name, value in cookies.items())


def cookie_collection_to_string(cookies: Any) -> str:
    if isinstance(cookies, str):
        return cookies.strip()
    if isinstance(cookies, Mapping):
        return cookie_mapping_to_string(cookies)
    if isinstance(cookies, list):
        pairs = []
        for cookie in cookies:
            if not isinstance(cookie, Mapping):
                continue
            name = str(cookie.get("name", "")).strip()
            value = str(cookie.get("value", "")).strip()
            if name:
                pairs.append(f"{name}={value}")
        return "; ".join(pairs)
    return ""


def parse_cookie_string(cookie_string: str, domain: str = ".quark.cn", path: str = "/") -> list[dict[str, Any]]:
    cookies = []
    for name, value in cookie_string_to_dict(cookie_string).items():
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": path,
            }
        )
    return cookies


def merge_cookie_strings(base_cookie_string: str, incoming_cookie_string: str) -> str:
    merged = cookie_string_to_dict(base_cookie_string)
    for name, value in cookie_string_to_dict(incoming_cookie_string).items():
        merged[name] = value
    return cookie_mapping_to_string(merged)


def _load_cookie_json(cookie_file: Path) -> Any:
    try:
        with open(cookie_file, "r", encoding="utf-8-sig") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def load_quark_cookie_payload(
    config_dir: Optional[Path] = None,
    include_legacy: bool = True,
) -> Optional[Any]:
    candidates = [get_quark_cookie_file(config_dir)]
    if include_legacy:
        candidates.append(get_legacy_cookie_file(config_dir))

    for cookie_file in candidates:
        if not cookie_file.exists():
            continue
        payload = _load_cookie_json(cookie_file)
        if payload:
            return payload
    return None


def load_quark_cookie_string(
    config_dir: Optional[Path] = None,
    include_legacy: bool = True,
) -> Optional[str]:
    payload = load_quark_cookie_payload(config_dir=config_dir, include_legacy=include_legacy)
    if not payload:
        return None

    if not isinstance(payload, Mapping):
        cookie_string = cookie_collection_to_string(payload)
        return cookie_string or None

    cookie_string = str(payload.get("cookie_string", "")).strip()
    if cookie_string:
        return cookie_string

    cookies = payload.get("cookies")
    cookie_string = cookie_collection_to_string(cookies)
    return cookie_string or None


def save_quark_cookie_string(
    cookie_string: str,
    *,
    config_dir: Optional[Path] = None,
    source: str = "unknown",
    extra_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized_cookie_string = cookie_mapping_to_string(cookie_string_to_dict(cookie_string))
    payload: Dict[str, Any] = {
        "cookies": parse_cookie_string(normalized_cookie_string),
        "cookie_string": normalized_cookie_string,
        "timestamp": int(time.time()),
        "source": source,
    }
    if extra_fields:
        payload.update(extra_fields)

    cookie_file = get_quark_cookie_file(config_dir)
    with open(cookie_file, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    return payload


def clear_quark_cookie_storage(
    config_dir: Optional[Path] = None,
    *,
    include_legacy: bool = True,
) -> list[Path]:
    removed_files: list[Path] = []
    candidates = [get_quark_cookie_file(config_dir)]
    if include_legacy:
        candidates.append(get_legacy_cookie_file(config_dir))

    for cookie_file in candidates:
        if cookie_file.exists():
            cookie_file.unlink()
            removed_files.append(cookie_file)

    return removed_files
