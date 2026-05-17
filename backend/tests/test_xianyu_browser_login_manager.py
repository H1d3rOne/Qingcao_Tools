from pathlib import Path

from xianyu_client.cookie_store import load_xianyu_cookie_string

from app.modules.xianyu.browser_login import XianyuBrowserLoginManager


def test_browser_login_manager_keeps_single_active_session(tmp_path: Path):
    manager = XianyuBrowserLoginManager(config_dir=tmp_path)

    first = manager.create_session(
        qrcode_image='data:image/png;base64,first',
        cleanup=None,
        expires_in=300,
    )
    second = manager.create_session(
        qrcode_image='data:image/png;base64,second',
        cleanup=None,
        expires_in=300,
    )

    assert first.session_id != second.session_id
    assert manager.get_session(first.session_id) is None
    assert manager.get_session(second.session_id).qrcode_image == 'data:image/png;base64,second'


def test_browser_login_manager_persists_cookie_on_success(tmp_path: Path):
    manager = XianyuBrowserLoginManager(config_dir=tmp_path)
    session = manager.create_session(
        qrcode_image='data:image/png;base64,qr',
        cleanup=None,
        expires_in=300,
    )

    result = manager.mark_success(
        session.session_id,
        cookie_string='cna=test; cookie2=abc; unb=user',
    )

    assert result['is_logged_in'] is True
    assert result['status'] == 'success'
    assert load_xianyu_cookie_string(config_dir=tmp_path) == 'cna=test; cookie2=abc; unb=user'
