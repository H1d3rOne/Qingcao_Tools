"""Lock down the exact HTTP request shape for /chat/completions calls.

之前用 `content=` + `ensure_ascii=False` 的手搓姿势触发了部分 OpenAI 兼容网关的
坑（LiteLLM / one-gpt 等翻译层丢 content）。这里锁定请求必须与 OpenAI Python SDK
等价：`json=` 序列化（ASCII 转义）+ `Content-Type: application/json; charset=utf-8`。
"""
from __future__ import annotations

import json

import httpx
import pytest

from app.modules.xianyu.schemas import XianyuChatAiProvider
from app.modules.xianyu.service import XianyuService


@pytest.mark.asyncio
async def test_chat_ai_request_uses_standard_openai_shape(monkeypatch):
    service = XianyuService()
    provider = XianyuChatAiProvider(
        id="p1",
        name="test",
        base_url="https://gateway.example.com/v1",
        active_model="gpt-5.4",
        system_prompt="hi",
        api_key_configured=True,
        api_key_masked="sk-****1234",
        is_active=True,
    )
    monkeypatch.setattr(
        service.chat_ai_store,
        "load_secret_api_key",
        lambda _pid: "sk-test-key-12345678",
    )

    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["headers"] = dict(request.headers)
        body_bytes = await request.aread()
        captured["body_bytes"] = body_bytes
        captured["body"] = json.loads(body_bytes)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "好的"}, "finish_reason": "stop"}]},
        )

    reply = await service._request_chat_ai_reply(
        provider=provider,
        messages=[
            {"role": "system", "content": "你是闲鱼客服"},
            {"role": "user", "content": "你好"},
        ],
        transport=httpx.MockTransport(handler),
    )

    assert reply == "好的"
    # URL must be base_url + /chat/completions, no trailing slash issues
    assert captured["url"] == "https://gateway.example.com/v1/chat/completions"
    assert captured["method"] == "POST"
    # Required auth + content-type headers present
    assert captured["headers"]["authorization"] == "Bearer sk-test-key-12345678"
    assert captured["headers"]["content-type"] == "application/json; charset=utf-8"
    assert captured["headers"]["accept"] == "application/json"
    # Minimal payload matches XianYuApis / ChatBox default: model + messages + standard params
    assert "model" in captured["body"]
    assert "messages" in captured["body"]
    assert captured["body"]["model"] == "gpt-5.4"
    assert len(captured["body"]["messages"]) == 2
    # Body must be ASCII-escaped JSON (matches OpenAI Python SDK default serialization)
    assert b"\\u4f60" in captured["body_bytes"] or b"\\u4F60" in captured["body_bytes"]
    # Raw UTF-8 Chinese bytes must NOT appear in the body
    assert "你好".encode("utf-8") not in captured["body_bytes"]


@pytest.mark.asyncio
async def test_chat_ai_surface_gateway_errors(monkeypatch):
    service = XianyuService()
    provider = XianyuChatAiProvider(
        id="p1",
        name="test",
        base_url="https://gateway.example.com/v1",
        active_model="gpt-5.4",
        system_prompt="",
        api_key_configured=True,
        api_key_masked="sk-****1234",
        is_active=True,
    )
    monkeypatch.setattr(
        service.chat_ai_store, "load_secret_api_key", lambda _pid: "sk-test"
    )

    async def handler(_: httpx.Request) -> httpx.Response:
        # Gateway returns 200 but empty content — the real failure mode user hit.
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": None, "reasoning_content": None},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"completion_tokens": 13, "total_tokens": 20},
            },
        )

    with pytest.raises(ValueError) as exc_info:
        await service._request_chat_ai_reply(
            provider=provider,
            messages=[{"role": "user", "content": "hi"}],
            transport=httpx.MockTransport(handler),
        )

    err = str(exc_info.value)
    assert "空回复" in err
    assert "finish_reason=stop" in err
    assert "completion_tokens" in err  # usage surfaced


@pytest.mark.asyncio
async def test_chat_ai_detects_reasoning_model_gateway_translation_bug(monkeypatch):
    """用户的真实事故：gpt-5.4 经过网关路由到 Responses API，翻译回 chat.completion 时丢 content。"""
    service = XianyuService()
    provider = XianyuChatAiProvider(
        id="p1",
        name="test",
        base_url="https://gateway.example.com/v1",
        active_model="gpt-5.4",
        system_prompt="",
        api_key_configured=True,
        api_key_masked="sk-****1234",
        is_active=True,
    )
    monkeypatch.setattr(
        service.chat_ai_store, "load_secret_api_key", lambda _pid: "sk-test"
    )

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "resp_02941f0a56a55ec70169e79ad1c3d481909e40ac22896a8de1",
                "object": "chat.completion",
                "model": "gpt-5.4",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "reasoning_content": None,
                            "tool_calls": None,
                        },
                        "finish_reason": "stop",
                        "native_finish_reason": "stop",
                    }
                ],
                "usage": {
                    "completion_tokens": 84,
                    "prompt_tokens": 38,
                    "total_tokens": 122,
                    "completion_tokens_details": {"reasoning_tokens": 10},
                },
            },
        )

    with pytest.raises(ValueError) as exc_info:
        await service._request_chat_ai_reply(
            provider=provider,
            messages=[{"role": "user", "content": "hi"}],
            transport=httpx.MockTransport(handler),
        )

    err = str(exc_info.value)
    # The error must explicitly blame the gateway translation bug and suggest
    # switching to a non-reasoning model — anything less leaves the user
    # stuck debugging their own code.
    assert "推测" in err
    assert "74" in err  # answer_tokens = 84 - 10
    assert "非推理模型" in err
    assert "gpt-4o" in err

