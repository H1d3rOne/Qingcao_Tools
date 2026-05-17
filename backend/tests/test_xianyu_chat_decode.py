"""Tests for XianyuService._decode_message_data decrypt fallback.

The upstream `wss-goofish.dingtalk.com` push carries base64-encoded MsgPack
binary payloads that need the goofish JS `decrypt()` helper to unpack. These
tests verify the fallback wiring without requiring a Node runtime for the
common cases, and a smoke test (Node-gated) for the real decrypt path.
"""
from __future__ import annotations

import json
import shutil

import pytest

from app.modules.xianyu import service as service_module
from app.modules.xianyu.service import XianyuService


def test_decode_uses_decrypt_fallback_when_other_parsers_fail(monkeypatch):
    svc = XianyuService()

    decrypted_payload = json.dumps(
        {
            "1": {
                "2": "cid-x@goofish",
                "10": {
                    "senderUserId": "222",
                    "reminderContent": "在吗？",
                    "reminderTitle": "买家A",
                },
            }
        }
    )

    call_count = {"n": 0}

    def fake_decrypt(data: str) -> str:
        call_count["n"] += 1
        return decrypted_payload

    monkeypatch.setattr(service_module, "xianyu_decrypt", fake_decrypt)

    # A string that is valid base64 but whose decoded bytes are not JSON.
    # In production this is the base64 MsgPack blob from syncPushPackage.
    import base64

    fake_encoded = base64.b64encode(b"\x01\x02\x03not-json").decode("ascii")
    result = svc._decode_message_data(fake_encoded)

    assert call_count["n"] == 1
    assert result["json_objects"], "decrypt result should populate json_objects"
    assert result["json_objects"][0]["1"]["10"]["senderUserId"] == "222"
    assert result["sender_user_id"] == "222"
    assert result["reminder_content"] == "在吗？"
    assert result["nickname"] == "买家A"

    candidate = svc._extract_ai_candidate({"biz_type": 40000, "decoded": result})
    assert candidate is not None
    assert candidate["cid"] == "cid-x@goofish"
    assert candidate["sender_uid"] == "222"
    assert candidate["text"] == "在吗？"
    assert candidate["sender_name"] == "买家A"


def test_decode_skips_decrypt_when_payload_is_plain_json(monkeypatch):
    svc = XianyuService()
    call_count = {"n": 0}

    def fake_decrypt(data: str) -> str:
        call_count["n"] += 1
        return ""

    monkeypatch.setattr(service_module, "xianyu_decrypt", fake_decrypt)

    raw = json.dumps({"1": {"2": "cid-y@goofish", "10": {"senderUserId": "333"}}})
    result = svc._decode_message_data(raw)

    assert call_count["n"] == 0
    assert result["sender_user_id"] == "333"


def test_decode_ignores_decrypt_none_and_falls_through(monkeypatch):
    svc = XianyuService()
    monkeypatch.setattr(service_module, "xianyu_decrypt", lambda _: None)

    # base64-decodable, contains an embedded JSON snippet that the brace scanner
    # should still pick up as a last resort.
    import base64

    text = 'prefix{"senderUserId":"444","reminderContent":"hi"}suffix'
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    result = svc._decode_message_data(encoded)

    assert result["sender_user_id"] == "444"


@pytest.mark.skipif(shutil.which("node") is None, reason="node runtime not available")
def test_real_js_decrypt_extracts_sender_fields():
    """Smoke test against the bundled goofish JS using a real base64 sample."""
    svc = XianyuService()

    # Sample from XianYuApis/static/goofish_js_version_2.js bottom comments.
    sample = (
        "ggGLAYEBtTIyMDI2NDA5MTgwNzlAZ29vZmlzaAKzNDc4MTI4NzAwMDBAZ29vZmlzaAOx"
        "MzQwMjM5MTQ3MjUwMy5QTk0EAAXPAAABlYW04bIGggFlA4UBoAKjMTExA6AEAQXaADR7"
        "ImF0VXNlcnMiOltdLCJjb250ZW50VHlwZSI6MSwidGV4dCI6eyJ0ZXh0IjoiMTExIn19"
        "BwIIAQkACoupX3BsYXRmb3Jtp2FuZHJvaWSmYml6VGFn2gBBeyJzb3VyY2VJZCI6IlM6"
        "MSIsIm1lc3NhZ2VJZCI6ImYzNjkwMmVmZjQ1NDQ1YmRiMmQxYjBmZDE2OGY4MjY0In2s"
        "ZGV0YWlsTm90aWNlozExMadleHRKc29u2gBLeyJxdWlja1JlcGx5IjoiMSIsIm1lc3Nh"
        "Z2VJZCI6ImYzNjkwMmVmZjQ1NDQ1YmRiMmQxYjBmZDE2OGY4MjY0IiwidGFnIjoidSJ9"
        "r3JlbWluZGVyQ29udGVudKMxMTGucmVtaW5kZXJOb3RpY2W15Y+R5p2l5LiA5p2h5paw"
        "5raI5oGvrXJlbWluZGVyVGl0bGWmc2hh5L+uq3JlbWluZGVyVXJs2gCbZmxlYW1hcmtl"
        "dDovL21lc3NhZ2VfY2hhdD9pdGVtSWQ9ODk3NzQyNzQ4MDExJnBlZXJVc2VySWQ9MjIw"
        "MjY0MDkxODA3OSZwZWVyVXNlck5pY2s9dCoqKjEmc2lkPTQ3ODEyODcwMDAwJm1lc3Nh"
        "Z2VJZD1mMzY5MDJlZmY0NTQ0NWJkYjJkMWIwZmQxNjhmODI2NCZhZHY9bm+sc2VuZGVy"
        "VXNlcklkrTIyMDI2NDA5MTgwNzmuc2VuZGVyVXNlclR5cGWhMKtzZXNzaW9uVHlwZaEx"
        "DAEDgahuZWVkUHVzaKR0cnVl"
    )

    result = svc._decode_message_data(sample)
    assert result["sender_user_id"] == "2202640918079"
    assert result["reminder_content"] == "111"
    assert result["nickname"] == "sha修"

    candidate = svc._extract_ai_candidate({"biz_type": 40000, "decoded": result})
    assert candidate is not None
    assert candidate["cid"] == "47812870000@goofish"
    assert candidate["sender_uid"] == "2202640918079"
