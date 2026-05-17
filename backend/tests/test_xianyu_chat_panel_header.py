from pathlib import Path


def _read_chat_panel() -> str:
    return Path(__file__).resolve().parents[2].joinpath('web-vue/src/views/xianyu/components/XianyuChatPanel.vue').read_text(encoding='utf-8')


def test_chat_panel_left_list_uses_peer_avatar_and_nickname_but_right_header_keeps_item_context():
    source = _read_chat_panel()

    assert "v-if=\"session.peer_avatar\"" in source
    assert "{{ session.title }}" in source

    assert ":src=\"activeSession.item_image\"" in source
    assert ":alt=\"activeSession.item_title || activeSession.title\"" in source
    assert "<strong>{{ activeSession.item_title || '闲鱼一对一会话' }}</strong>" in source
    assert "<span>{{ activeSession.peer_display_name || activeSession.title || '未知卖家' }}</span>" in source
