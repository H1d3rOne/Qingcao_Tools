import asyncio
import hashlib
import json
import platform
import re
import shlex
import subprocess
import threading
import time
from typing import Optional
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlparse, urlunparse

from app.modules.wechat.constants import (
    LOCAL_SERVER_HOST,
    LOCAL_SERVER_PORT,
    PROXY_HOST,
    PROXY_PORT,
)

ctx = None
http = None
options = None
DumpMaster = None


def _ensure_mitmproxy_imported() -> None:
    global ctx, http, options, DumpMaster
    if ctx is not None and http is not None and options is not None and DumpMaster is not None:
        return

    from mitmproxy import ctx as mitm_ctx, http as mitm_http, options as mitm_options
    from mitmproxy.tools.dump import DumpMaster as MitmDumpMaster

    ctx = mitm_ctx
    http = mitm_http
    options = mitm_options
    DumpMaster = MitmDumpMaster


def hex_md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def get_platform() -> str:
    system = platform.system()
    if system == "Darwin":
        return "macos"
    if system == "Windows":
        return "windows"
    return "linux"


def _looks_like_permission_error(text: str) -> bool:
    lowered = (text or "").lower()
    keywords = [
        "requires admin privileges",
        "authorizationcreate() failed",
        "permission denied",
        "operation not permitted",
        "not permitted",
    ]
    return any(keyword in lowered for keyword in keywords)


def _run_macos_commands(commands) -> tuple[bool, list]:
    failures = []
    has_permission_error = False

    for cmd in commands:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            failures.append((cmd, result))
            err_text = f"{result.stdout}\n{result.stderr}"
            if _looks_like_permission_error(err_text):
                has_permission_error = True

    if not failures:
        return True, []

    if has_permission_error:
        joined_cmd = " && ".join(shlex.join(cmd) for cmd in commands)
        escaped = joined_cmd.replace("\\", "\\\\").replace('"', '\\"')
        admin_result = subprocess.run(
            ["osascript", "-e", f'do shell script "{escaped}" with administrator privileges'],
            capture_output=True,
            text=True,
        )
        if admin_result.returncode == 0:
            return True, []
        return False, [(["osascript", "-e", "do shell script ... with administrator privileges"], admin_result)]

    return False, failures


def get_network_services_macos() -> list[str]:
    try:
        result = subprocess.run(["networksetup", "-listallnetworkservices"], capture_output=True, text=True)
        if result.returncode != 0:
            return ["Wi-Fi"]

        services = []
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("An asterisk") or line.startswith("*"):
                continue
            services.append(line)
        return services or ["Wi-Fi"]
    except Exception:
        return ["Wi-Fi"]


class WechatProxyAddon:
    def __init__(self):
        self.report_seen = {}
        self.report_ttl_seconds = 300
        self.max_report_seen = 5000
        self.version_tag = "34e90de1478e8a54af7fd56d4a3a7102"

    def _normalize_media_url(self, media_url: str) -> str:
        if not media_url:
            return ""
        parsed = urlparse(media_url)
        if parsed.scheme and parsed.netloc:
            return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        return media_url.split("?", 1)[0]

    def _build_report_key(self, data: dict) -> str:
        media = (data.get("media") or [{}])[0]
        decode_key = (media.get("decodeKey") or "").strip()
        if decode_key:
            return f"decode:{decode_key}"

        normalized_url = self._normalize_media_url(media.get("url", ""))
        parts = [
            normalized_url,
            str(media.get("fileSize", "")),
            str(media.get("videoPlayLen", "")),
            media.get("coverUrl", ""),
            data.get("description", ""),
        ]
        return "media:" + hex_md5("|".join(parts))

    def _prune_seen_keys(self, now_ts: float) -> None:
        expired = [
            key for key, last_seen in self.report_seen.items()
            if now_ts - last_seen > self.report_ttl_seconds
        ]
        for key in expired:
            self.report_seen.pop(key, None)

        if len(self.report_seen) > self.max_report_seen:
            oldest_key = min(self.report_seen, key=self.report_seen.get)
            self.report_seen.pop(oldest_key, None)

    def _should_forward_report(self, data: dict) -> tuple[bool, str]:
        now_ts = time.time()
        self._prune_seen_keys(now_ts)

        dedupe_key = self._build_report_key(data)
        last_seen = self.report_seen.get(dedupe_key)
        if last_seen and now_ts - last_seen <= self.report_ttl_seconds:
            return False, dedupe_key

        self.report_seen[dedupe_key] = now_ts
        return True, dedupe_key

    def _forward_to_local_server(self, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = urlrequest.Request(
            f"http://{LOCAL_SERVER_HOST}:{LOCAL_SERVER_PORT}/",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        opener = urlrequest.build_opener(urlrequest.ProxyHandler({}))
        with opener.open(req, timeout=2) as resp:
            resp.read(1)

    def _handle_video_report(self, data: dict) -> None:
        if not data.get("media"):
            return

        should_forward, dedupe_key = self._should_forward_report(data)
        if not should_forward:
            ctx.log.info(f"Skip duplicated report: {dedupe_key}")
            return

        try:
            self._forward_to_local_server(data)
        except (urlerror.URLError, TimeoutError, OSError) as exc:
            ctx.log.info(f"Forward report failed: {exc}")

    def request(self, flow) -> None:
        if flow.request.pretty_host not in ("localhost", "127.0.0.1"):
            return

        if flow.request.port != PROXY_PORT or not flow.request.path.startswith("/__shipinhao_report"):
            return

        flow.response = http.Response.make(200, b"ok", {"Content-Type": "text/plain"})
        try:
            if flow.request.method == "POST":
                try:
                    data = json.loads(flow.request.content.decode())
                    self._handle_video_report(data)
                except json.JSONDecodeError:
                    pass
        except Exception as exc:
            ctx.log.info(f"proxy request err: {exc}")

    def response(self, flow) -> None:
        host = flow.request.pretty_host

        if host == "channels.weixin.qq.com":
            if "/web/pages/feed" in flow.request.path or "/web/pages/home" in flow.request.path:
                try:
                    content = flow.response.content.decode("utf-8")
                    content = content.replace('.js"', f'.js?v={self.version_tag}"')
                    flow.response.content = content.encode("utf-8")
                except Exception as exc:
                    ctx.log.info(f"Error modifying response: {exc}")

        elif host == "res.wx.qq.com":
            try:
                if flow.request.path.endswith(f".js?v={self.version_tag}"):
                    content = flow.response.content.decode("utf-8")
                    content = content.replace('.js"', f'.js?v={self.version_tag}"')
                    flow.response.content = content.encode("utf-8")

                if "web/web-finder/res/js/virtual_svg-icons-register.publish" in flow.request.path:
                    content = flow.response.content.decode("utf-8")
                    inject_code = '''
                    get media(){
                        if(this.objectDesc){
                            try{
                                const media = this.objectDesc.media && this.objectDesc.media[0] ? this.objectDesc.media[0] : null;
                                const dedupeKey = media
                                    ? [media.url || "", media.urlToken || "", media.decodeKey || "", this.objectDesc.description || ""].join("|")
                                    : JSON.stringify(this.objectDesc);
                                if(!window.__shipinhao_sent_keys){
                                    window.__shipinhao_sent_keys = {};
                                }
                                if(!window.__shipinhao_sent_keys[dedupeKey]){
                                    window.__shipinhao_sent_keys[dedupeKey] = 1;
                                    fetch("http://127.0.0.1:8090/__shipinhao_report", {
                                        method: "POST",
                                        mode: "no-cors",
                                        headers: {
                                            'Content-Type': 'application/json'
                                        },
                                        body: JSON.stringify(this.objectDesc),
                                    });
                                }
                            }catch(e){}
                        };
                    '''
                    content = re.sub(r"get\s*media\s*\(\)\s*\{", inject_code, content)
                    flow.response.content = content.encode("utf-8")
            except Exception as exc:
                ctx.log.info(f"Error modifying JS: {exc}")


class ProxyController:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._master = None
        self._ready = threading.Event()
        self._system_proxy_enabled = False
        self._last_error: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    @property
    def system_proxy_enabled(self) -> bool:
        return self._system_proxy_enabled

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def start(self) -> None:
        if self.is_running:
            return

        self._last_error = None
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="wechat-proxy-server", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=10):
            raise RuntimeError("代理服务器启动超时")
        if self._last_error:
            raise RuntimeError(self._last_error)

    def stop(self) -> None:
        self._disable_system_proxy()

        if self._loop and self._master:
            try:
                self._loop.call_soon_threadsafe(self._master.shutdown)
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=6)

        self._thread = None
        self._master = None
        self._loop = None
        self._ready.clear()

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            _ensure_mitmproxy_imported()
            opts = options.Options(listen_host="0.0.0.0", listen_port=PROXY_PORT)
            master = DumpMaster(opts, loop=self._loop, with_termlog=False, with_dumper=False)
            master.addons.add(WechatProxyAddon())
            self._master = master
            self._system_proxy_enabled = self._enable_system_proxy()
            self._ready.set()
            self._loop.run_until_complete(master.run())
        except Exception as exc:
            self._last_error = str(exc)
            self._ready.set()
        finally:
            self._disable_system_proxy()
            if self._loop and not self._loop.is_closed():
                self._loop.close()
            self._loop = None
            self._master = None

    def _enable_system_proxy(self) -> bool:
        current_platform = get_platform()

        if current_platform == "macos":
            services = get_network_services_macos()
            enabled_services = []
            for service in services:
                commands = [
                    ["networksetup", "-setwebproxy", service, PROXY_HOST, str(PROXY_PORT)],
                    ["networksetup", "-setsecurewebproxy", service, PROXY_HOST, str(PROXY_PORT)],
                    ["networksetup", "-setproxybypassdomains", service, "localhost", "127.0.0.1", "::1", "local", "*.local"],
                    ["networksetup", "-setwebproxystate", service, "on"],
                    ["networksetup", "-setsecurewebproxystate", service, "on"],
                ]
                ok, _ = _run_macos_commands(commands)
                if ok:
                    enabled_services.append(service)
            self._system_proxy_enabled = bool(enabled_services)
            return self._system_proxy_enabled

        if current_platform == "windows":
            try:
                subprocess.run(
                    ["netsh", "winhttp", "set", "proxy", f"{PROXY_HOST}:{PROXY_PORT}"],
                    check=True,
                    shell=True,
                )
                import winreg

                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings",
                    0,
                    winreg.KEY_WRITE,
                )
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"{PROXY_HOST}:{PROXY_PORT}")
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "localhost;127.0.0.1;::1;<local>")
                winreg.CloseKey(key)
                self._system_proxy_enabled = True
                return True
            except Exception:
                self._system_proxy_enabled = False
                return False

        self._system_proxy_enabled = False
        return False

    def _disable_system_proxy(self) -> bool:
        current_platform = get_platform()
        success = False

        if current_platform == "macos":
            services = get_network_services_macos()
            for service in services:
                commands = [
                    ["networksetup", "-setwebproxystate", service, "off"],
                    ["networksetup", "-setsecurewebproxystate", service, "off"],
                ]
                ok, _ = _run_macos_commands(commands)
                success = ok or success

        elif current_platform == "windows":
            try:
                subprocess.run(["netsh", "winhttp", "reset", "proxy"], check=True, shell=True)
                import winreg

                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings",
                    0,
                    winreg.KEY_WRITE,
                )
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
                try:
                    winreg.DeleteValue(key, "ProxyServer")
                except FileNotFoundError:
                    pass
                try:
                    winreg.DeleteValue(key, "ProxyOverride")
                except FileNotFoundError:
                    pass
                winreg.CloseKey(key)
                success = True
            except Exception:
                success = False

        self._system_proxy_enabled = False
        return success
