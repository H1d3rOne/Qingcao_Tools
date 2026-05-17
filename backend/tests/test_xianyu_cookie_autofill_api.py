from fastapi.testclient import TestClient

from app.main import app
from xianyu_client.cookie_store import save_xianyu_cookie_string


def test_settings_cookie_xianyu_full_reads_local_cookie_file(tmp_path, monkeypatch):
    monkeypatch.setenv('XIANYU_CONFIG_DIR', str(tmp_path))
    save_xianyu_cookie_string(
        'cna=test-cna; cookie2=test-cookie2; __puus=test-puus',
        config_dir=tmp_path,
        source='manual_input',
    )

    client = TestClient(app)
    response = client.get('/api/v1/settings/cookie/xianyu/full')

    assert response.status_code == 200
    payload = response.json()
    assert payload['success'] is True
    assert payload['data']['configured'] is True
    assert payload['data']['cookie'] == 'cna=test-cna; cookie2=test-cookie2; __puus=test-puus'
