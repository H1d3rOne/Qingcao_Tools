from pathlib import Path
import asyncio

import pytest

from app.core.config import settings as app_settings
from app.modules.quark.services.quark_service import QuarkService
from app.modules.settings.service import SettingsService
from quark_client.auth.api_login import APILogin
from quark_client.config import get_config_dir
from quark_client.cookie_store import (
    QUARK_COOKIE_FILE_NAME,
    load_quark_cookie_string,
    load_quark_cookie_payload,
    merge_cookie_strings,
    save_quark_cookie_string,
)


def test_save_quark_cookie_string_uses_dedicated_file(tmp_path, monkeypatch):
    monkeypatch.setenv("QUARK_CONFIG_DIR", str(tmp_path))

    cookie_string = "__pus=pus-value; __kps=kps-value; __uid=uid-value"
    save_quark_cookie_string(cookie_string, source="manual_input")

    quark_cookie_file = tmp_path / QUARK_COOKIE_FILE_NAME

    assert quark_cookie_file.exists()
    assert not (tmp_path / "cookies.json").exists()

    payload = load_quark_cookie_payload()
    assert payload is not None
    assert payload["cookie_string"] == cookie_string
    assert payload["source"] == "manual_input"


def test_merge_cookie_strings_replaces_existing_values_and_keeps_others():
    merged = merge_cookie_strings(
        "__pus=pus-value; __kps=kps-value; __uid=uid-value",
        "__puus=puus-value; __kps=new-kps-value",
    )

    assert "__pus=pus-value" in merged
    assert "__uid=uid-value" in merged
    assert "__puus=puus-value" in merged
    assert "__kps=new-kps-value" in merged
    assert "__kps=kps-value" not in merged


def test_api_login_enriches_cookie_string_with_puus_from_flush_response(monkeypatch):
    login = APILogin(timeout=1)

    class DummyResponse:
        def __init__(self):
            self.headers = {
                "set-cookie": "__puus=puus-value; Domain=.quark.cn; Path=/; HttpOnly"
            }

        def raise_for_status(self):
            return None

    def fake_get(url, params=None):
        assert url == "https://drive-pc.quark.cn/1/clouddrive/auth/pc/flush"
        assert params == {"pr": "ucpro", "fr": "pc", "uc_param_str": ""}
        return DummyResponse()

    monkeypatch.setattr(login.client, "get", fake_get)

    enriched = login.enrich_cookie_string_with_puus(
        "__pus=pus-value; __kps=kps-value; __uid=uid-value"
    )

    assert "__puus=puus-value" in enriched
    assert "__pus=pus-value" in enriched
    assert "__kps=kps-value" in enriched
    assert "__uid=uid-value" in enriched


def test_settings_service_reads_quark_cookie_state_from_dedicated_file(tmp_path, monkeypatch):
    monkeypatch.setenv("QUARK_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(app_settings.cookies, "quark", "", raising=False)

    cookie_string = "__pus=pus-value; __kps=kps-value; __uid=uid-value; __puus=puus-value"
    save_quark_cookie_string(cookie_string, config_dir=tmp_path, source="manual_input")

    service = SettingsService()
    status = asyncio.run(service.get_status())
    cookie_info = asyncio.run(service.get_cookie_settings())

    assert status.quark_cookie_configured is True
    assert cookie_info.quark_configured is True
    assert cookie_info.quark_preview.startswith("__pus=pus-value")
    assert cookie_info.quark_preview


def test_settings_service_update_quark_cookie_saves_dedicated_file_instead_of_yaml(tmp_path, monkeypatch):
    monkeypatch.setenv("QUARK_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(app_settings.cookies, "quark", "", raising=False)

    config_file = tmp_path / "config.yaml"
    config_file.write_text("cookies:\n  douyin: existing-dy\n", encoding="utf-8")

    service = SettingsService()
    service.config_path = config_file

    cookie_string = "__pus=pus-value; __kps=kps-value; __uid=uid-value"
    success = asyncio.run(service.update_quark_cookie(cookie_string))

    assert success is True
    assert load_quark_cookie_string(config_dir=tmp_path, include_legacy=False) == cookie_string
    yaml_text = config_file.read_text(encoding="utf-8")
    assert "quark:" not in yaml_text


def test_quark_service_logout_clears_saved_cookie_file_even_without_client(tmp_path, monkeypatch):
    monkeypatch.setenv("QUARK_CONFIG_DIR", str(tmp_path))

    cookie_string = "__pus=pus-value; __kps=kps-value; __uid=uid-value"
    save_quark_cookie_string(cookie_string, config_dir=tmp_path, source="manual_input")

    QuarkService._instance = None
    service = QuarkService()
    service._client = None
    service._is_logged_in = True

    result = service.logout()

    assert result["success"] is True
    assert load_quark_cookie_string(config_dir=tmp_path, include_legacy=False) is None
