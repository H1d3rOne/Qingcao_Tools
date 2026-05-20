from pathlib import Path
import json

from app.modules.xianyu.ai_store import XianyuChatAiStore
from app.modules.xianyu.schemas import XianyuChatAiConfigUpdateRequest


def test_ai_store_loads_defaults_and_masks_missing_key(tmp_path: Path):
    store = XianyuChatAiStore(
        config_path=tmp_path / 'xianyu_ai_config.json',
        sessions_path=tmp_path / 'xianyu_ai_sessions.json',
    )

    config = store.load_config()

    assert config.enabled is False
    assert config.base_url == 'https://api.openai.com/v1'
    assert config.model == 'gpt-4.1-mini'
    assert config.api_key_configured is False
    assert config.api_key_masked == ''


def test_ai_store_preserves_existing_api_key_when_update_omits_new_value(tmp_path: Path):
    store = XianyuChatAiStore(
        config_path=tmp_path / 'xianyu_ai_config.json',
        sessions_path=tmp_path / 'xianyu_ai_sessions.json',
    )
    store.save_config(
        XianyuChatAiConfigUpdateRequest(
            enabled=True,
            base_url='https://example.com/v1',
            api_key='sk-test-12345678',
            model='gpt-4.1-mini',
            system_prompt='reply briefly',
            temperature=0.3,
        )
    )

    config = store.save_config(
        XianyuChatAiConfigUpdateRequest(
            enabled=False,
            base_url='https://example.com/v1',
            api_key='',
            model='gpt-4.1-mini',
            system_prompt='reply briefly',
            temperature=0.2,
        )
    )

    assert config.enabled is False
    assert config.api_key_configured is True
    assert config.api_key_masked.endswith('5678')
    assert store.load_secret_api_key() == 'sk-test-12345678'


def test_ai_store_roundtrips_session_states(tmp_path: Path):
    store = XianyuChatAiStore(
        config_path=tmp_path / 'xianyu_ai_config.json',
        sessions_path=tmp_path / 'xianyu_ai_sessions.json',
    )

    store.set_session_enabled('cid-1', True)
    store.set_session_enabled('cid-2', False)

    assert store.get_session_enabled('cid-1') is True
    assert store.get_session_enabled('cid-2') is False
    assert [item.model_dump() for item in store.list_session_states(['cid-1', 'cid-2'])] == [
        {'cid': 'cid-1', 'enabled': True},
        {'cid': 'cid-2', 'enabled': False},
    ]


def test_ai_store_restores_providers_from_backup_when_config_becomes_stub(tmp_path: Path):
    config_path = tmp_path / 'xianyu_ai_config.json'
    store = XianyuChatAiStore(
        config_path=config_path,
        sessions_path=tmp_path / 'xianyu_ai_sessions.json',
    )
    store.save_config(
        XianyuChatAiConfigUpdateRequest(
            enabled=False,
            base_url='https://example.com/v1',
            api_key='sk-test-12345678',
            model='gpt-4.1-mini',
            system_prompt='reply briefly',
            temperature=0.3,
        )
    )
    assert (tmp_path / 'xianyu_ai_config.json.bak').exists()

    config_path.write_text(json.dumps({'enabled': True}), encoding='utf-8')

    config = store.load_config()

    assert config.enabled is True
    assert len(config.providers) == 1
    assert config.providers[0].base_url == 'https://example.com/v1'
    assert config.providers[0].api_key_configured is True
    assert store.load_secret_api_key() == 'sk-test-12345678'
