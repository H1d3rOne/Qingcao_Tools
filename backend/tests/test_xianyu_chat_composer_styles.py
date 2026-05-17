from pathlib import Path


def _read_chat_panel() -> str:
    return Path(__file__).resolve().parents[2].joinpath('web-vue/src/views/xianyu/components/XianyuChatPanel.vue').read_text(encoding='utf-8')


def test_chat_composer_textarea_uses_dark_theme_colors():
    source = _read_chat_panel()

    assert ':deep(.el-textarea__inner)' in source
    assert 'background: rgba(var(--app-surface-rgb), 0.96) !important;' in source
    assert 'color: rgb(var(--app-text-strong-rgb)) !important;' in source
    assert '-webkit-text-fill-color: rgb(var(--app-text-strong-rgb)) !important;' in source
    assert 'caret-color: rgb(var(--app-text-strong-rgb)) !important;' in source
