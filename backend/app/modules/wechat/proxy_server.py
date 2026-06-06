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


def get_proxy_start_timeout_seconds() -> int:
    """mitmproxy 冷启动超时时间。

    Windows 10/11 ARM64 首次导入 mitmproxy/cryptography 或初始化证书时明显更慢，
    原来的 10 秒容易误报“代理服务器启动超时”。
    """
    system = platform.system()
    machine = (platform.machine() or "").lower()
    if system == "Windows" and ("arm" in machine or "aarch64" in machine):
        return 60
    if system == "Windows":
        return 45
    return 30


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


def get_windows_proxy_override() -> str:
    return (
        "localhost;127.0.0.1;::1;0.0.0.0;10.*;172.16.*;172.17.*;172.18.*;172.19.*;"
        "172.20.*;172.21.*;172.22.*;172.23.*;172.24.*;172.25.*;172.26.*;172.27.*;"
        "172.28.*;172.29.*;172.30.*;172.31.*;192.168.*;<local>"
    )


def notify_windows_proxy_settings_changed() -> None:
    """通知 WinINet/系统设置刷新代理配置。

    只写注册表时，Windows 10/11 的“系统代理”界面和已运行应用不一定立即刷新；
    InternetSetOptionW 会广播设置变更。
    """
    try:
        import ctypes

        internet_set_option = ctypes.windll.Wininet.InternetSetOptionW
        internet_set_option(0, 39, 0, 0)  # INTERNET_OPTION_SETTINGS_CHANGED
        internet_set_option(0, 37, 0, 0)  # INTERNET_OPTION_REFRESH
    except Exception:
        pass


def _windows_proxy_value(values: dict, name: str, default=None):
    item = values.get(name)
    if item is None:
        return default
    return item[1]


def _windows_proxy_bool(values: dict, name: str) -> bool:
    try:
        return int(_windows_proxy_value(values, name, 0) or 0) != 0
    except (TypeError, ValueError):
        return False


def is_windows_proxy_active(values: dict) -> bool:
    return (
        _windows_proxy_bool(values, "ProxyEnable")
        or bool(str(_windows_proxy_value(values, "AutoConfigURL", "") or "").strip())
        or _windows_proxy_bool(values, "AutoDetect")
    )


def sync_windows_proxy_settings_best_effort(values: dict) -> bool:
    """用 WinINet API 刷新当前用户代理。

    微软文档说明全局代理可通过当前用户 Internet Settings 配置并调用
    INTERNET_OPTION_SETTINGS_CHANGED / INTERNET_OPTION_REFRESH 让 WinINet 重读。
    INTERNET_OPTION_PER_CONNECTION_OPTION 可同步默认连接配置，但不同 Windows
    版本/策略下可能失败，不能因为刷新失败阻断 mitmproxy 启动。
    """
    success = False
    try:
        import ctypes
        from ctypes import wintypes

        INTERNET_OPTION_PER_CONNECTION_OPTION = 75
        INTERNET_PER_CONN_FLAGS = 1
        INTERNET_PER_CONN_PROXY_SERVER = 2
        INTERNET_PER_CONN_PROXY_BYPASS = 3
        INTERNET_PER_CONN_AUTOCONFIG_URL = 4

        PROXY_TYPE_DIRECT = 0x00000001
        PROXY_TYPE_PROXY = 0x00000002
        PROXY_TYPE_AUTO_PROXY_URL = 0x00000004
        PROXY_TYPE_AUTO_DETECT = 0x00000008

        class INTERNET_PER_CONN_OPTION_VALUE(ctypes.Union):
            _fields_ = [
                ("dwValue", wintypes.DWORD),
                ("pszValue", wintypes.LPWSTR),
                ("ftValue", wintypes.FILETIME),
            ]

        class INTERNET_PER_CONN_OPTION(ctypes.Structure):
            _fields_ = [
                ("dwOption", wintypes.DWORD),
                ("Value", INTERNET_PER_CONN_OPTION_VALUE),
            ]

        class INTERNET_PER_CONN_OPTION_LIST(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("pszConnection", wintypes.LPWSTR),
                ("dwOptionCount", wintypes.DWORD),
                ("dwOptionError", wintypes.DWORD),
                ("pOptions", ctypes.POINTER(INTERNET_PER_CONN_OPTION)),
            ]

        proxy_enabled = _windows_proxy_bool(values, "ProxyEnable")
        proxy_server = str(_windows_proxy_value(values, "ProxyServer", "") or "").strip()
        proxy_bypass = str(_windows_proxy_value(values, "ProxyOverride", "") or "").strip()
        auto_config_url = str(_windows_proxy_value(values, "AutoConfigURL", "") or "").strip()
        auto_detect = _windows_proxy_bool(values, "AutoDetect")

        flags = 0
        if proxy_enabled and proxy_server:
            flags |= PROXY_TYPE_PROXY
        if auto_config_url:
            flags |= PROXY_TYPE_AUTO_PROXY_URL
        if auto_detect:
            flags |= PROXY_TYPE_AUTO_DETECT
        if flags == 0:
            flags = PROXY_TYPE_DIRECT

        option_items = [("flags", INTERNET_PER_CONN_FLAGS, flags)]
        if proxy_server:
            option_items.append(("server", INTERNET_PER_CONN_PROXY_SERVER, proxy_server))
        if proxy_bypass:
            option_items.append(("bypass", INTERNET_PER_CONN_PROXY_BYPASS, proxy_bypass))
        if auto_config_url:
            option_items.append(("autoconfig", INTERNET_PER_CONN_AUTOCONFIG_URL, auto_config_url))

        options_array = (INTERNET_PER_CONN_OPTION * len(option_items))()
        for index, (_, option, value) in enumerate(option_items):
            options_array[index].dwOption = option
            if option == INTERNET_PER_CONN_FLAGS:
                options_array[index].Value.dwValue = value
            else:
                options_array[index].Value.pszValue = value

        option_list = INTERNET_PER_CONN_OPTION_LIST()
        option_list.dwSize = ctypes.sizeof(INTERNET_PER_CONN_OPTION_LIST)
        option_list.pszConnection = None
        option_list.dwOptionCount = len(option_items)
        option_list.dwOptionError = 0
        option_list.pOptions = options_array

        wininet = ctypes.windll.Wininet
        ok = wininet.InternetSetOptionW(
            0,
            INTERNET_OPTION_PER_CONNECTION_OPTION,
            ctypes.byref(option_list),
            ctypes.sizeof(option_list),
        )
        success = bool(ok)
    except Exception:
        success = False
    finally:
        notify_windows_proxy_settings_changed()
    return success


class WechatProxyAddon:
    def __init__(
        self,
        proxy_port: int = PROXY_PORT,
        local_server_host: str = LOCAL_SERVER_HOST,
        local_server_port: int = LOCAL_SERVER_PORT,
    ):
        self.proxy_port = proxy_port
        self.local_server_host = local_server_host
        self.local_server_port = local_server_port
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
            f"http://{self.local_server_host}:{self.local_server_port}/",
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

        if flow.request.port != self.proxy_port or not flow.request.path.startswith("/__shipinhao_report"):
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
                                    fetch("__SHIPINHAO_REPORT_URL__", {
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
                    inject_code = inject_code.replace(
                        "__SHIPINHAO_REPORT_URL__",
                        f"http://127.0.0.1:{self.proxy_port}/__shipinhao_report",
                    )
                    content = re.sub(r"get\s*media\s*\(\)\s*\{", inject_code, content)
                    flow.response.content = content.encode("utf-8")
            except Exception as exc:
                ctx.log.info(f"Error modifying JS: {exc}")


class ProxyController:
    def __init__(
        self,
        proxy_host: str = PROXY_HOST,
        proxy_port: int = PROXY_PORT,
        local_server_host: str = LOCAL_SERVER_HOST,
        local_server_port: int = LOCAL_SERVER_PORT,
    ):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.local_server_host = local_server_host
        self.local_server_port = local_server_port
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._master = None
        self._ready = threading.Event()
        self._system_proxy_enabled = False
        self._last_error: Optional[str] = None
        self._startup_stage = "未启动"
        self._stop_requested = False
        self._windows_previous_proxy_settings: Optional[dict] = None
        self._windows_winhttp_proxy_changed = False

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop_requested)

    @property
    def system_proxy_enabled(self) -> bool:
        return self._system_proxy_enabled

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            if self._stop_requested:
                raise RuntimeError("代理服务器上次启动仍在清理中，请稍后重试")
            return

        self._last_error = None
        self._startup_stage = "准备启动"
        self._stop_requested = False
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="wechat-proxy-server", daemon=True)
        self._thread.start()
        timeout = get_proxy_start_timeout_seconds()
        if not self._ready.wait(timeout=timeout):
            self._stop_requested = True
            self._last_error = (
                f"代理服务器启动超时（等待 {timeout} 秒，当前阶段：{self._startup_stage}）。"
                "Windows 10/11 ARM64 首次初始化 mitmproxy 可能较慢；如果反复出现，"
                "请检查 mitmproxy 是否安装完整、端口是否被占用，或安全软件是否拦截 Python。"
            )
            raise RuntimeError(self._last_error)
        if self._last_error:
            raise RuntimeError(self._last_error)

    def stop(self) -> None:
        self._stop_requested = True
        self._disable_system_proxy()

        if self._loop and self._master:
            try:
                self._loop.call_soon_threadsafe(self._master.shutdown)
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=6)

        if self._thread and self._thread.is_alive():
            self._last_error = self._last_error or "代理服务器停止超时，请稍后重试"
            return

        self._thread = None
        self._master = None
        self._loop = None
        self._ready.clear()
        self._startup_stage = "已停止"
        self._stop_requested = False

    def _run(self) -> None:
        self._startup_stage = "初始化事件循环"
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._startup_stage = "导入 mitmproxy"
            _ensure_mitmproxy_imported()
            if self._stop_requested:
                return

            self._startup_stage = f"初始化 mitmproxy 代理端口 {self.proxy_port}"
            opts = options.Options(listen_host="0.0.0.0", listen_port=self.proxy_port)
            master = DumpMaster(opts, loop=self._loop, with_termlog=False, with_dumper=False)
            master.addons.add(
                WechatProxyAddon(
                    proxy_port=self.proxy_port,
                    local_server_host=self.local_server_host,
                    local_server_port=self.local_server_port,
                )
            )
            self._master = master
            if self._stop_requested:
                return

            self._startup_stage = "设置系统代理"
            self._system_proxy_enabled = self._enable_system_proxy()
            if self._stop_requested:
                return

            self._startup_stage = "启动代理主循环"
            self._ready.set()
            self._loop.run_until_complete(master.run())
        except Exception as exc:
            self._last_error = str(exc)
            self._ready.set()
        finally:
            self._startup_stage = "停止中"
            self._disable_system_proxy()
            if self._loop and not self._loop.is_closed():
                self._loop.close()
            self._loop = None
            self._master = None
            self._startup_stage = "已停止"
            self._stop_requested = False

    def _read_windows_proxy_settings(self) -> dict:
        import winreg

        names = ("ProxyEnable", "ProxyServer", "ProxyOverride", "AutoConfigURL", "AutoDetect")
        values = {name: None for name in names}
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        except FileNotFoundError:
            return values

        with key:
            for name in values:
                try:
                    value, value_type = winreg.QueryValueEx(key, name)
                    values[name] = (value_type, value)
                except FileNotFoundError:
                    pass
        return values

    def _write_windows_proxy_settings(self, values: dict) -> None:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        access = winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, access) as key:
            for name, item in values.items():
                if item is None:
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
                    continue
                value_type, value = item
                winreg.SetValueEx(key, name, 0, value_type, value)
        notify_windows_proxy_settings_changed()

    def _enable_windows_user_proxy(self) -> None:
        import winreg

        self._startup_stage = "检测 Windows 系统代理"
        if self._windows_previous_proxy_settings is None:
            self._windows_previous_proxy_settings = self._read_windows_proxy_settings()

        if is_windows_proxy_active(self._windows_previous_proxy_settings):
            self._startup_stage = "覆盖已有 Windows 系统代理"
        else:
            self._startup_stage = "开启 Windows 系统代理"

        proxy_server = f"{self.proxy_host}:{self.proxy_port}"
        next_settings = {
            # 手动代理已开启时覆盖旧地址；未开启时打开手动代理。
            "ProxyEnable": (winreg.REG_DWORD, 1),
            "ProxyServer": (winreg.REG_SZ, proxy_server),
            "ProxyOverride": (winreg.REG_SZ, get_windows_proxy_override()),
            # PAC/自动检测会干扰手动代理，监听期间先关闭，停止监听时恢复。
            "AutoConfigURL": None,
            "AutoDetect": (winreg.REG_DWORD, 0),
        }
        self._write_windows_proxy_settings(next_settings)
        sync_windows_proxy_settings_best_effort(next_settings)

        current = self._read_windows_proxy_settings()
        enabled = (current.get("ProxyEnable") or (None, 0))[1]
        server = (current.get("ProxyServer") or (None, ""))[1]
        if int(enabled or 0) != 1 or str(server) != proxy_server:
            raise RuntimeError("Windows 当前用户代理写入后校验失败")

    def _restore_windows_user_proxy(self) -> bool:
        try:
            if self._windows_previous_proxy_settings is not None:
                self._write_windows_proxy_settings(self._windows_previous_proxy_settings)
                sync_windows_proxy_settings_best_effort(self._windows_previous_proxy_settings)
                self._windows_previous_proxy_settings = None
            return True
        except Exception:
            return False

    def _enable_windows_winhttp_proxy_best_effort(self) -> None:
        try:
            result = subprocess.run(
                [
                    "netsh",
                    "winhttp",
                    "set",
                    "proxy",
                    f"proxy-server={self.proxy_host}:{self.proxy_port}",
                    f"bypass-list={get_windows_proxy_override()}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self._windows_winhttp_proxy_changed = result.returncode == 0
        except Exception:
            pass

    def _disable_windows_winhttp_proxy_best_effort(self) -> None:
        if not self._windows_winhttp_proxy_changed:
            return
        try:
            result = subprocess.run(
                ["netsh", "winhttp", "reset", "proxy"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                self._windows_winhttp_proxy_changed = False
        except Exception:
            pass

    def _enable_system_proxy(self) -> bool:
        current_platform = get_platform()

        if current_platform == "macos":
            services = get_network_services_macos()
            enabled_services = []
            for service in services:
                commands = [
                    ["networksetup", "-setwebproxy", service, self.proxy_host, str(self.proxy_port)],
                    ["networksetup", "-setsecurewebproxy", service, self.proxy_host, str(self.proxy_port)],
                    [
                        "networksetup",
                        "-setproxybypassdomains",
                        service,
                        "localhost",
                        "127.0.0.1",
                        "::1",
                        "0.0.0.0",
                        "local",
                        "*.local",
                        "10.*",
                        "172.16.*",
                        "172.17.*",
                        "172.18.*",
                        "172.19.*",
                        "172.20.*",
                        "172.21.*",
                        "172.22.*",
                        "172.23.*",
                        "172.24.*",
                        "172.25.*",
                        "172.26.*",
                        "172.27.*",
                        "172.28.*",
                        "172.29.*",
                        "172.30.*",
                        "172.31.*",
                        "192.168.*",
                    ],
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
                # 视频号页面/浏览器走的是 WinINet 当前用户系统代理；
                # netsh winhttp 在普通用户权限下可能失败，不能让它阻断注册表代理写入。
                self._enable_windows_user_proxy()
                self._enable_windows_winhttp_proxy_best_effort()
                self._system_proxy_enabled = True
                return True
            except Exception as exc:
                self._system_proxy_enabled = False
                raise RuntimeError(f"设置 Windows 系统代理失败: {exc}") from exc

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
            self._disable_windows_winhttp_proxy_best_effort()
            success = self._restore_windows_user_proxy()

        self._system_proxy_enabled = False
        return success
