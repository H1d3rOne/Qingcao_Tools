import httpx
import pytest

from app.modules.xianyu.service import XianyuService


class FakeReusableChatClient:
    def __init__(self, connected: bool = True):
        self.connected = connected
        self.close_calls = 0

    def is_connected(self) -> bool:
        return self.connected

    async def close(self):
        self.close_calls += 1
        self.connected = False


@pytest.mark.asyncio
async def test_open_chat_ws_client_does_not_retry_login_token_after_chat_auth_error(monkeypatch):
    service = XianyuService()
    created = []
    refreshed = {'count': 0}

    async def fake_refresh_chat_runtime_token():
        refreshed['count'] += 1

    async def fake_create_connected_chat_ws_client():
        if not created:
            created.append('failed')
            raise ValueError('闲鱼登录已过期，请重新登录闲鱼后更新 Cookie')
        client = FakeReusableChatClient(True)
        created.append(client)
        return client

    monkeypatch.setattr(service, '_get_xianyu_cookie_value', lambda: 'cookie')
    monkeypatch.setattr(service, '_refresh_chat_runtime_token', fake_refresh_chat_runtime_token)
    monkeypatch.setattr(service, '_create_connected_chat_ws_client', fake_create_connected_chat_ws_client)

    try:
        with pytest.raises(ValueError, match='闲鱼登录已过期'):
            await service.open_chat_ws_client()
    finally:
        await service.stop_chat_keepalive()

    assert refreshed['count'] == 1
    # 鉴权/风控错误后不立刻第二次 login.token + /reg，避免会话切换时连续握手加重风控。
    assert created == ['failed']


def test_sync_runtime_cookie_persists_chat_auth_cookie_whitelist(monkeypatch):
    service = XianyuService()
    captured = {}

    monkeypatch.setattr(
        service,
        '_get_xianyu_cookie_value',
        lambda: 'cna=old-cna; cookie2=old-cookie2; _m_h5_tk=oldtk_1',
    )

    def fake_save(cookie_string: str, *, source: str = 'unknown', **kwargs):
        captured['cookie_string'] = cookie_string
        captured['source'] = source
        return {}

    monkeypatch.setattr('app.modules.xianyu.service.save_xianyu_cookie_string', fake_save)

    client = httpx.AsyncClient()
    client.cookies.set('cookie2', 'new-cookie2', domain='.goofish.com')
    client.cookies.set('sgcookie', 'sg-value', domain='.goofish.com')
    client.cookies.set('t', 'token-value', domain='.goofish.com')
    client.cookies.set('_m_h5_tk', 'newtk_2', domain='.goofish.com')
    client.cookies.set('unrelated', 'skip-me', domain='.example.com')

    service._sync_runtime_cookie(client)

    assert 'cookie2=new-cookie2' in captured['cookie_string']
    assert 'sgcookie=sg-value' in captured['cookie_string']
    assert 't=token-value' in captured['cookie_string']
    assert '_m_h5_tk=newtk_2' in captured['cookie_string']
    assert 'unrelated=skip-me' not in captured['cookie_string']
    assert captured['source'] == 'runtime_refresh'


def test_extract_error_keeps_rgv587_signal():
    service = XianyuService()

    message = service._extract_error(
        {
            'ret': [
                'FAIL_SYS_USER_VALIDATE',
                'RGV587_ERROR::SM::哎哟喂,被挤爆啦,请稍后重试',
            ]
        }
    )

    assert 'FAIL_SYS_USER_VALIDATE' in message
    assert 'RGV587_ERROR' in message


@pytest.mark.asyncio
async def test_chat_keepalive_tick_refreshes_runtime_and_drops_disconnected_shared_client(monkeypatch):
    service = XianyuService()
    refreshed = {'count': 0}
    stale_client = FakeReusableChatClient(False)
    service._shared_chat_client = stale_client

    monkeypatch.setattr(service, '_get_xianyu_cookie_value', lambda: 'cookie')

    async def fake_refresh_chat_runtime_token():
        refreshed['count'] += 1

    monkeypatch.setattr(service, '_refresh_chat_runtime_token', fake_refresh_chat_runtime_token)

    ran = await service._chat_keepalive_tick()

    assert ran is True
    assert refreshed['count'] == 1
    assert stale_client.close_calls == 1
    assert service._shared_chat_client is None


@pytest.mark.asyncio
async def test_diagnose_chat_runtime_returns_risk_blocked_with_captcha_url(monkeypatch):
    service = XianyuService()

    monkeypatch.setattr(service, '_get_xianyu_cookie_value', lambda: 'cookie')

    async def fake_open_chat_ws_client():
        raise ValueError(
            '闲鱼接口被风控拦截，请在浏览器中打开以下链接完成验证后重新更新 Cookie：https://example.com/punish'
        )

    monkeypatch.setattr(service, 'open_chat_ws_client', fake_open_chat_ws_client)

    result = await service.diagnose_chat_runtime()

    assert result.ok is False
    assert result.status == 'risk_blocked'
    assert result.captcha_url == 'https://example.com/punish'


@pytest.mark.asyncio
async def test_build_chat_bootstrap_ignores_non_chat_fingerprint_device_id(monkeypatch, tmp_path):
    service = XianyuService()
    service._chat_device_store_path = tmp_path / 'xianyu_chat_devices.json'
    captured = {}

    class _FakeLogin:
        fingerprint = {'deviceId': 'fingerprint-device-id'}

    service._auth_login = _FakeLogin()

    async def fake_execute_api(client, api_name, api_url, payload, extra_params=None):
        if api_name == service.chat_login_token_api_name:
            captured['payload'] = dict(payload)
            return {'data': {'accessToken': 'token-1'}}
        if api_name == service.chat_login_user_api_name:
            return {'data': {'userId': '111', 'mainUserId': '111'}}
        raise AssertionError(f'unexpected api {api_name}')

    monkeypatch.setattr(service, '_execute_api', fake_execute_api)

    async with httpx.AsyncClient() as client:
        client.cookies.set('unb', '111', domain='.goofish.com')
        bootstrap = await service._build_chat_bootstrap(client, include_token=True)

    assert captured['payload']['deviceId'] != 'fingerprint-device-id'
    assert captured['payload']['deviceId'].endswith('-111')
    assert bootstrap['device_id'].endswith('-111')


@pytest.mark.asyncio
async def test_build_chat_bootstrap_uses_unb_suffix_for_generated_device_id(monkeypatch, tmp_path):
    service = XianyuService()
    service._chat_device_store_path = tmp_path / 'xianyu_chat_devices.json'
    captured = {}

    class _FakeLogin:
        fingerprint = {}

    service._auth_login = _FakeLogin()

    async def fake_execute_api(client, api_name, api_url, payload, extra_params=None):
        if api_name == service.chat_login_token_api_name:
            captured['payload'] = dict(payload)
            return {'data': {'accessToken': 'token-1'}}
        if api_name == service.chat_login_user_api_name:
            return {'data': {'userId': '111', 'mainUserId': '111'}}
        raise AssertionError(f'unexpected api {api_name}')

    monkeypatch.setattr(service, '_execute_api', fake_execute_api)

    async with httpx.AsyncClient() as client:
        client.cookies.set('unb', '2218827902934', domain='.goofish.com')
        bootstrap = await service._build_chat_bootstrap(client, include_token=True)

    assert captured['payload']['deviceId'].endswith('-2218827902934')
    assert bootstrap['device_id'].endswith('-2218827902934')
