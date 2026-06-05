import os


def pytest_configure():
    """避免本机代理环境变量影响离线单元测试的 httpx Client 初始化。"""
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(key, None)
