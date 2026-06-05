from pathlib import Path


def read_xianyu_login_page() -> str:
    return Path(__file__).resolve().parents[2].joinpath(
        "web-vue/src/views/xianyu/login/index.vue"
    ).read_text(encoding="utf-8")


def test_xianyu_login_page_uses_cookie_login_only():
    source = read_xianyu_login_page()

    assert "<el-tabs" not in source
    assert "<el-tab-pane" not in source
    assert "扫码登录" not in source
    assert "<el-collapse" not in source
    assert "请输入闲鱼 Cookie" in source
    assert "从本地已保存 Cookie 填充" in source
