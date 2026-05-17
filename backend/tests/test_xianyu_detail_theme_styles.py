from pathlib import Path
import re


def _read_xianyu_view() -> str:
    return Path(__file__).resolve().parents[2].joinpath("web-vue/src/views/xianyu/index.vue").read_text(encoding="utf-8")


def _block(source: str, selector: str) -> str:
    pattern = re.compile(re.escape(selector) + r"\s*\{(.*?)\n\}", re.S)
    match = pattern.search(source)
    assert match, f"missing selector: {selector}"
    return match.group(1)


def test_detail_description_uses_separate_themed_surface_block():
    source = _read_xianyu_view()

    assert 'class="detail-desc-block theme-surface-soft"' in source

    block = _block(source, ".detail-desc-block")
    desc = _block(source, ".detail-desc")
    paragraph = _block(source, ".detail-desc p")

    assert "background: rgba(var(--app-surface-alt-rgb), 0.92);" in block or "background: rgba(var(--app-surface-rgb), 0.96);" in block
    assert "border: 1px solid rgba(var(--app-border-rgb)," in block
    assert "color: rgb(var(--app-text-strong-rgb)) !important;" in desc
    assert "color: rgb(var(--app-text-strong-rgb)) !important;" in paragraph


def test_detail_meta_and_actions_keep_theme_text_colors():
    source = _read_xianyu_view()

    meta = _block(source, ".detail-meta-list span")
    actions = _block(source, ".detail-actions")
    secondary_button = _block(source, ".detail-actions :deep(.el-button:not(.el-button--primary))")

    assert "color: rgb(var(--app-text-muted-rgb)) !important;" in meta
    assert "grid-template-columns" in actions
    assert "color: rgb(var(--app-text-rgb));" in secondary_button


def test_detail_section_still_contains_contact_and_open_actions():
    source = _read_xianyu_view()

    assert 'class="detail-actions"' in source
    assert '联系卖家' in source
    assert '打开原站详情' in source
