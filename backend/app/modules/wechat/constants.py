PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8090
LOCAL_SERVER_HOST = "127.0.0.1"
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
