import asyncio
from pathlib import Path

from app.modules.settings.service import SettingsService
from xianyu_client.auth.api_login import XianyuAPILogin
from xianyu_client.cookie_store import (
    XIANYU_COOKIE_FILE_NAME,
    load_xianyu_cookie_string,
    normalize_xianyu_cookie_input,
    save_xianyu_cookie_string,
)


def test_save_xianyu_cookie_string_uses_dedicated_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XIANYU_CONFIG_DIR", str(tmp_path))

    cookie_string = "cna=test; cookie2=abc; __puus=puus-value"
    save_xianyu_cookie_string(cookie_string, source="manual_input")

    cookie_file = tmp_path / XIANYU_COOKIE_FILE_NAME

    assert cookie_file.exists()
    assert load_xianyu_cookie_string(config_dir=tmp_path) == cookie_string


def test_api_login_extracts_goofish_cookie_string_from_session():
    login = XianyuAPILogin(timeout=1)
    login.client.cookies.set("cna", "test-cna", domain=".goofish.com")
    login.client.cookies.set("cookie2", "cookie2-value", domain=".goofish.com")
    login.client.cookies.set("unrelated", "value", domain=".example.com")

    cookie_string = login.extract_xianyu_cookie_string()

    assert "cna=test-cna" in cookie_string
    assert "cookie2=cookie2-value" in cookie_string
    assert "unrelated=value" not in cookie_string


def test_settings_service_reads_xianyu_cookie_from_dedicated_file(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XIANYU_CONFIG_DIR", str(tmp_path))

    cookie_string = "cna=test; cookie2=abc; __puus=puus-value"
    save_xianyu_cookie_string(cookie_string, config_dir=tmp_path, source="manual_input")

    service = SettingsService()
    cookie_info = asyncio.run(service.get_cookie_settings())

    assert cookie_info.xianyu_configured is True
    assert cookie_info.xianyu_preview.startswith("cna=test")


import json


def test_api_login_loads_fingerprint_from_config(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XIANYU_CONFIG_DIR", str(tmp_path))
    fingerprint = {
        "ua": "ua-token",
        "bx_ua": "bx-ua-token",
        "bx_umidtoken": "bx-umid-token",
        "bx_et": "bx-et-token",
        "x_pipu2": "x-pipu2-token",
        "umidToken": "umid-token",
        "csrf_token": "csrf-token",
        "dynamic_fingerprints": [{"ua": "ua-1", "bx_ua": "bx-ua-1"}],
    }
    (tmp_path / 'xianyu_fingerprint.json').write_text(json.dumps(fingerprint), encoding='utf-8')

    login = XianyuAPILogin(timeout=1)

    assert login.fingerprint["ua"] == "ua-token"
    assert login.fingerprint["dynamic_fingerprints"][0]["bx_ua"] == "bx-ua-1"


def test_api_login_query_qrcode_sends_fingerprint_fields(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XIANYU_CONFIG_DIR", str(tmp_path))
    fingerprint = {
        "ua": "ua-token",
        "bx_ua": "bx-ua-token",
        "bx_umidtoken": "bx-umid-token",
        "bx_et": "bx-et-token",
        "x_pipu2": "x-pipu2-token",
        "umidToken": "umid-token",
        "csrf_token": "csrf-token",
        "ck": "cookie2-token",
        "navUserAgent": "custom-ua",
        "dynamic_fingerprints": [
            {
                "ua": "ua-token-1",
                "bx_ua": "bx-ua-token-1",
                "bx_umidtoken": "bx-umid-token-1",
                "bx_et": "bx-et-token-1",
                "x_pipu2": "x-pipu2-token-1",
            }
        ],
    }
    (tmp_path / 'xianyu_fingerprint.json').write_text(json.dumps(fingerprint), encoding='utf-8')

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"content": {"data": {"qrCodeStatus": "NEW"}}}

    def fake_post(url, data=None, timeout=None, headers=None):
        captured['url'] = url
        captured['data'] = dict(data or {})
        captured['headers'] = headers or {}
        return FakeResponse()

    login = XianyuAPILogin(timeout=1)
    monkeypatch.setattr(login.client, 'post', fake_post)

    result = login.query_qrcode(t='123', device_id='device-1', page_trace_id='trace-1')

    assert result['content']['data']['qrCodeStatus'] == 'NEW'
    assert captured['data']['ua'] == 'ua-token-1'
    assert captured['data']['bx-ua'] == 'bx-ua-token-1'
    assert captured['data']['bx-umidtoken'] == 'bx-umid-token-1'
    assert captured['data']['bx_et'] == 'bx-et-token-1'
    assert captured['data']['x-pipu2'] == 'x-pipu2-token-1'
    assert captured['data']['umidToken'] == 'umid-token'
    assert captured['data']['_csrf_token'] == 'csrf-token'
    assert captured['data']['ck'] == 'cookie2-token'
    assert captured['data']['deviceId'] == 'device-1'
    assert captured['data']['pageTraceId'] == 'trace-1'


def test_api_login_generates_cna_when_missing():
    login = XianyuAPILogin(timeout=1)

    cna = login._ensure_cna()

    assert cna
    assert login.client.cookies.get('cna', domain='.goofish.com') == cna


def test_normalize_xianyu_cookie_input_accepts_json_payload():
    payload = json.dumps(
        {
            "cookies": [
                {"name": "cna", "value": "test-cna"},
                {"name": "cookie2", "value": "cookie2-value"},
                {"name": "unb", "value": "123456"},
            ]
        },
        ensure_ascii=False,
    )

    normalized = normalize_xianyu_cookie_input(payload)

    assert normalized == "cna=test-cna; cookie2=cookie2-value; unb=123456"
