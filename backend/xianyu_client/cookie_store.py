"""
闲鱼 cookie 存储辅助。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Optional

from .config import get_config_dir

XIANYU_COOKIE_FILE_NAME = "xianyu_cookies.json"


def get_xianyu_cookie_file(config_dir: Optional[Path] = None) -> Path:
    directory = Path(config_dir or get_config_dir())
    directory.mkdir(parents=True, exist_ok=True)
    return directory / XIANYU_COOKIE_FILE_NAME


def cookie_string_to_dict(cookie_string: str) -> dict[str, str]:
    cookie_dict: dict[str, str] = {}
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
        pairs: list[str] = []
        for cookie in cookies:
            if not isinstance(cookie, Mapping):
                continue
            name = str(cookie.get("name", "")).strip()
            value = str(cookie.get("value", "")).strip()
            if name:
                pairs.append(f"{name}={value}")
        return "; ".join(pairs)
    return ""


def normalize_xianyu_cookie_input(cookie_input: Any) -> str:
    if cookie_input is None:
        return ""

    if isinstance(cookie_input, Mapping):
        if "cookie_string" in cookie_input:
            return normalize_xianyu_cookie_input(cookie_input.get("cookie_string"))
        if "cookies" in cookie_input:
            return normalize_xianyu_cookie_input(cookie_input.get("cookies"))
        if {"name", "value"} <= set(str(key) for key in cookie_input.keys()):
            name = str(cookie_input.get("name", "")).strip()
            value = str(cookie_input.get("value", "")).strip()
            return f"{name}={value}" if name else ""
        return cookie_mapping_to_string(
            {
                str(name).strip(): str(value).strip()
                for name, value in cookie_input.items()
                if str(name).strip()
            }
        )

    if isinstance(cookie_input, list):
        return cookie_collection_to_string(cookie_input)

    raw = str(cookie_input).strip()
    if not raw:
        return ""

    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()

    if raw[:1] in {"{", "["}:
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        if parsed is not None:
            return normalize_xianyu_cookie_input(parsed)

    cleaned = raw.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")
    return cookie_mapping_to_string(cookie_string_to_dict(cleaned))


def merge_cookie_strings(base_cookie_string: str, incoming_cookie_string: str) -> str:
    merged = cookie_string_to_dict(base_cookie_string)
    for name, value in cookie_string_to_dict(incoming_cookie_string).items():
        merged[name] = value
    return cookie_mapping_to_string(merged)


def parse_cookie_string(cookie_string: str, domain: str = ".goofish.com", path: str = "/") -> list[dict[str, Any]]:
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


def _load_cookie_json(cookie_file: Path) -> Any:
    try:
        with open(cookie_file, "r", encoding="utf-8-sig") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def load_xianyu_cookie_payload(
    config_dir: Optional[Path] = None,
) -> Optional[Any]:
    cookie_file = get_xianyu_cookie_file(config_dir)
    if not cookie_file.exists():
        return None
    return _load_cookie_json(cookie_file)


def load_xianyu_cookie_string(
    config_dir: Optional[Path] = None,
) -> Optional[str]:
    payload = load_xianyu_cookie_payload(config_dir=config_dir)
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


def save_xianyu_cookie_string(
    cookie_string: str,
    *,
    config_dir: Optional[Path] = None,
    source: str = "unknown",
    extra_fields: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    normalized_cookie_string = normalize_xianyu_cookie_input(cookie_string)
    payload: dict[str, Any] = {
        "cookies": parse_cookie_string(normalized_cookie_string),
        "cookie_string": normalized_cookie_string,
        "timestamp": int(time.time()),
        "source": source,
    }
    if extra_fields:
        payload.update(extra_fields)

    cookie_file = get_xianyu_cookie_file(config_dir)
    with open(cookie_file, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    return payload


def clear_xianyu_cookie_storage(config_dir: Optional[Path] = None) -> list[Path]:
    removed_files: list[Path] = []
    cookie_file = get_xianyu_cookie_file(config_dir)
    if cookie_file.exists():
        cookie_file.unlink()
        removed_files.append(cookie_file)
    return removed_files
