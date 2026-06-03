PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8090
LOCAL_SERVER_HOST = "127.0.0.1"
# 后端 API 默认占用 3121，本地接收服务默认错开，避免抢占 /api 端口。
LOCAL_SERVER_PORT = 3122
MITMPROXY_CERT_BASENAME = "mitmproxy"


def to_size(size) -> str:
    try:
        size = int(size)
    except (TypeError, ValueError):
        return "0B"

    if size >= 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024 * 1024):.2f}GB"
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.2f}MB"
    if size >= 1024:
        return f"{size / 1024:.2f}KB"
    return f"{size}B"
