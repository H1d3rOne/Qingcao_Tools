import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional


class _WechatVideoRequestHandler(BaseHTTPRequestHandler):
    server_version = "WechatLocalServer/1.0"

    def do_POST(self):
        if self.path != "/":
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._write_json({"error": "Invalid JSON"}, 400)
            return

        callback: Optional[Callable] = getattr(self.server, "on_video_payload", None)
        if callback is None:
            self._write_json({"error": "Server callback missing"}, 500)
            return

        try:
            callback(payload)
        except ValueError as exc:
            self._write_json({"error": str(exc)}, 400)
            return
        except Exception as exc:
            self._write_json({"error": str(exc)}, 500)
            return

        self._write_json({"success": True})

    def log_message(self, format, *args):
        return

    def _write_json(self, data, status_code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class LocalVideoServer:
    def __init__(self, host: str, port: int, on_video_payload: Callable):
        self.host = host
        self.port = port
        self.on_video_payload = on_video_payload
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._started = threading.Event()
        self._error: Optional[BaseException] = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.is_running:
            return

        self._started.clear()
        self._error = None

        def _serve():
            try:
                self._httpd = ThreadingHTTPServer((self.host, self.port), _WechatVideoRequestHandler)
                self._httpd.on_video_payload = self.on_video_payload
                self._started.set()
                self._httpd.serve_forever(poll_interval=0.5)
            except BaseException as exc:
                self._error = exc
                self._started.set()

        self._thread = threading.Thread(target=_serve, name="wechat-local-server", daemon=True)
        self._thread.start()
        if not self._started.wait(timeout=3):
            raise RuntimeError("本地服务器启动超时")
        if self._error:
            raise RuntimeError(str(self._error))

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None
        self._started.clear()
        self._error = None
