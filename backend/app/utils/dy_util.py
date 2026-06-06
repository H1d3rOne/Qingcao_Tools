import re
import sys
import time
import json
import os
import random
import base64
import hashlib
import urllib
from urllib.parse import unquote
from os import path
from pathlib import Path

import requests
requests.packages.urllib3.disable_warnings()
import subprocess
from functools import partial

subprocess.Popen = partial(subprocess.Popen, encoding="utf-8")
import execjs

# 获取脚本文件目录。execjs 的 cwd 指向 backend 根目录，确保 Node 能按
# backend/node_modules 解析 require('jsrsasign')，避免 Windows 下从 stdin
# 执行脚本时出现错误的模块查找路径。
BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = BACKEND_ROOT / "app" / "modules" / "douyin" / "scripts"

# 加载 JS 文件
dy_path = SCRIPTS_DIR / 'dy_ab.js'
sign_path = SCRIPTS_DIR / 'dy_live_sign.js'
bdm_signer_path = SCRIPTS_DIR / 'bdm_sign_vm.js'
bdm_live_path = SCRIPTS_DIR / 'bdm_live.js'

_dy_js = None
_sign_js = None

DOUYIN_LIVE_WEBCAST_SDK_VERSION = "1.0.15"


def _format_node_dependency_message(module_name=None):
    module_hint = f"（缺少 {module_name}）" if module_name else ""
    return f"后端 JS 依赖未安装{module_hint}，请在 backend 目录执行 npm ci 后重启后端"


def _extract_missing_node_module(message):
    match = re.search(r"Cannot find module ['\"]([^'\"]+)['\"]", message or "")
    return match.group(1) if match else None


def _ensure_node_modules(*module_names):
    missing = [
        module_name for module_name in module_names
        if not (BACKEND_ROOT / "node_modules" / module_name).exists()
    ]
    if missing:
        raise RuntimeError(_format_node_dependency_message(", ".join(missing)))


def _raise_friendly_js_error(exc, live_danmu=False):
    message = str(exc)
    missing_module = _extract_missing_node_module(message)
    if missing_module or "MODULE_NOT_FOUND" in message:
        raise RuntimeError(_format_node_dependency_message(missing_module)) from exc
    if (
        "Could not find an available JavaScript runtime" in message
        or "No such file or directory: 'node'" in message
        or "No such file or directory: \"node\"" in message
    ):
        raise RuntimeError("未找到 Node.js，请先安装 Node.js，并在 backend 目录执行 npm ci 后重启后端") from exc
    raise exc


def _compile_js(script_path, *module_names, live_danmu=False):
    if not script_path.exists():
        raise RuntimeError(f"抖音 JS 脚本缺失: {script_path}")
    _ensure_node_modules(*module_names)
    try:
        return execjs.compile(script_path.read_text(encoding="utf-8"), cwd=str(BACKEND_ROOT))
    except Exception as exc:
        _raise_friendly_js_error(exc, live_danmu=live_danmu)


def _get_dy_js():
    global _dy_js
    if _dy_js is None:
        _dy_js = _compile_js(dy_path, "jsrsasign")
    return _dy_js


def _get_sign_js():
    global _sign_js
    if _sign_js is None:
        _sign_js = _compile_js(sign_path, live_danmu=True)
    return _sign_js


def _call_js(get_context, function_name, *args):
    try:
        return get_context().call(function_name, *args)
    except Exception as exc:
        _raise_friendly_js_error(exc, live_danmu=get_context is _get_sign_js)


def trans_cookies(cookies_str):
    cookies = {
        # "douyin.com": "",
    }
    for i in cookies_str.split("; "):
        try:
            cookies[i.split('=')[0]] = '='.join(i.split('=')[1:])
        except:
            continue
    # cookies = {i.split('=')[0]: '='.join(i.split('=')[1:]) for i in cookies_str.split('; ')}
    return cookies


# 私信传obj, 其他的拼接
def generate_req_sign(e, priK):
    sign = _call_js(_get_dy_js, 'get_req_sign', e, priK)
    return sign


# 抖音默认 PC 指纹。真实请求会优先从 Cookie 中恢复浏览器 UA/屏幕/网络等信息，
# 这里仅作为 Cookie 不完整时的兜底值，避免各接口散落硬编码。
DEFAULT_DOUYIN_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0"
)


def _auth_cookie(auth):
    return getattr(auth, "cookie", None) or {}


def _stringify_bool(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _normal_number(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _parse_cookie_json(value):
    """解析 Cookie 中常见的多层 URL encode / JSON 字符串。"""
    if not value:
        return {}

    candidates = [value]
    current = value
    for _ in range(3):
        decoded = unquote(current)
        if decoded == current:
            break
        candidates.append(decoded)
        current = decoded

    for candidate in list(candidates):
        try:
            loaded = json.loads(candidate)
            if isinstance(loaded, str):
                try:
                    loaded = json.loads(unquote(loaded))
                except Exception:
                    loaded = json.loads(loaded)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            continue
    return {}


def _parse_druid_client_info(value):
    """解析 __druidClientInfo，主要用于恢复浏览器真实 User-Agent。"""
    if not value:
        return {}
    try:
        # 该 Cookie 通常是 base64(quote(json))。
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
        data = json.loads(unquote(decoded))
        return data if isinstance(data, dict) else {}
    except Exception:
        return _parse_cookie_json(value)


def _browser_major(version):
    match = re.match(r"(\d+)", version or "")
    return match.group(1) if match else "125"


def _parse_user_agent(user_agent):
    """从 UA 推断 Header 与平台参数。"""
    profile = {
        "user_agent": user_agent or DEFAULT_DOUYIN_USER_AGENT,
        "browser_name": "Edge",
        "browser_version": "125.0.0.0",
        "engine_name": "Blink",
        "engine_version": "125.0.0.0",
        "browser_platform": "Win32",
        "os_name": "Windows",
        "os_version": "10",
        "pc_libra_divert": "Windows",
        "sec_ch_ua_platform": '"Windows"',
        "sec_ch_ua": '"Microsoft Edge";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
    }

    ua = profile["user_agent"]
    chrome_match = re.search(r"Chrome/([\d.]+)", ua)
    edge_match = re.search(r"Edg/([\d.]+)", ua)
    firefox_match = re.search(r"Firefox/([\d.]+)", ua)
    safari_match = re.search(r"Version/([\d.]+).*Safari/", ua)

    if edge_match:
        version = edge_match.group(1)
        major = _browser_major(version)
        profile.update({
            "browser_name": "Edge",
            "browser_version": version,
            "engine_version": chrome_match.group(1) if chrome_match else version,
            "sec_ch_ua": f'"Microsoft Edge";v="{major}", "Chromium";v="{major}", "Not.A/Brand";v="24"',
        })
    elif chrome_match:
        version = chrome_match.group(1)
        major = _browser_major(version)
        profile.update({
            "browser_name": "Chrome",
            "browser_version": version,
            "engine_version": version,
            "sec_ch_ua": f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not/A)Brand";v="99"',
        })
    elif firefox_match:
        version = firefox_match.group(1)
        profile.update({
            "browser_name": "Firefox",
            "browser_version": version,
            "engine_name": "Gecko",
            "engine_version": version,
            "sec_ch_ua": '"Not.A/Brand";v="24"',
        })
    elif safari_match:
        version = safari_match.group(1)
        profile.update({
            "browser_name": "Safari",
            "browser_version": version,
            "engine_name": "WebKit",
            "engine_version": version,
            "sec_ch_ua": '"Not.A/Brand";v="24"',
        })

    if "Macintosh" in ua or "Mac OS X" in ua:
        os_version = "10.15.7"
        match = re.search(r"Mac OS X ([\d_]+)", ua)
        if match:
            os_version = match.group(1).replace("_", ".")
        profile.update({
            "browser_platform": "MacIntel",
            "os_name": "Mac OS",
            "os_version": os_version,
            "pc_libra_divert": "Mac",
            "sec_ch_ua_platform": '"macOS"',
        })
    elif "Windows" in ua:
        os_version = "10"
        match = re.search(r"Windows NT ([\d.]+)", ua)
        if match and match.group(1).startswith("6."):
            os_version = match.group(1)
        profile.update({
            "browser_platform": "Win32",
            "os_name": "Windows",
            "os_version": os_version,
            "pc_libra_divert": "Windows",
            "sec_ch_ua_platform": '"Windows"',
        })
    elif "Linux" in ua:
        profile.update({
            "browser_platform": "Linux x86_64",
            "os_name": "Linux",
            "os_version": "",
            "pc_libra_divert": "Linux",
            "sec_ch_ua_platform": '"Linux"',
        })

    return profile


def get_douyin_browser_profile(auth=None):
    """构建与 Cookie/UA 一致的抖音 PC 浏览器指纹参数。"""
    cookie = _auth_cookie(auth)
    druid_info = _parse_druid_client_info(cookie.get("__druidClientInfo"))
    user_agent = druid_info.get("userAgent") or DEFAULT_DOUYIN_USER_AGENT
    profile = _parse_user_agent(user_agent)

    stream_params = _parse_cookie_json(cookie.get("stream_recommend_feed_params"))
    if not stream_params:
        stream_params = {}

    defaults = {
        "device_platform": "webapp",
        "aid": "6383",
        "channel": "channel_pc_web",
        "pc_client_type": "1",
        "update_version_code": "170400",
        "version_code": "170400",
        "version_name": "17.4.0",
        "cookie_enabled": "true",
        "screen_width": "1707",
        "screen_height": "960",
        "browser_language": "zh-CN",
        "browser_online": "true",
        "platform": "PC",
        "downlink": "10",
        "effective_type": "4g",
        "round_trip_time": "100",
        "cpu_core_num": "8",
        "device_memory": "8",
        "support_h265": "1" if cookie.get("hevc_supported", "true") == "true" else "0",
        "support_dash": "1" if cookie.get("is_dash_user", "1") in ("1", "true", "True") else "0",
    }
    profile.update(defaults | profile)

    for key in (
        "cookie_enabled",
        "screen_width",
        "screen_height",
        "browser_online",
        "cpu_core_num",
        "device_memory",
        "downlink",
        "effective_type",
        "round_trip_time",
    ):
        if key in stream_params and stream_params[key] not in (None, ""):
            value = stream_params[key]
            profile[key] = _stringify_bool(value) if isinstance(value, bool) else _normal_number(value)

    if cookie.get("dy_swidth"):
        profile["screen_width"] = cookie["dy_swidth"]
    if cookie.get("dy_sheight"):
        profile["screen_height"] = cookie["dy_sheight"]
    if cookie.get("device_web_cpu_core"):
        profile["cpu_core_num"] = cookie["device_web_cpu_core"]
    if cookie.get("device_web_memory_size"):
        profile["device_memory"] = cookie["device_web_memory_size"]

    druid_field_map = {
        "clientWidth": "client_width",
        "clientHeight": "client_height",
        "width": "inner_width",
        "height": "inner_height",
        "devicePixelRatio": "device_pixel_ratio",
    }
    for source_key, target_key in druid_field_map.items():
        value = druid_info.get(source_key)
        if value not in (None, ""):
            profile[target_key] = _normal_number(value)

    profile["uifid"] = cookie.get("UIFID") or cookie.get("UIFID_TEMP") or ""
    verify_fp = getattr(auth, "verifyFp", None) or cookie.get("s_v_web_id") or ""
    profile["verifyFp"] = verify_fp
    profile["fp"] = verify_fp
    profile["msToken"] = getattr(auth, "msToken", None) or cookie.get("msToken") or generate_msToken()
    profile["cookie"] = getattr(auth, "cookie_str", "") or ""

    return profile


def _run_bdm_signer(full_url, *, data="", user_agent=None, env=None, page_url=None, timeout=20):
    """运行 bdms VM 签名器，返回完整 signed_url 与 a_bogus。"""
    if not bdm_signer_path.exists() or not bdm_live_path.exists():
        raise RuntimeError("bdms 签名脚本缺失，请检查 backend/app/modules/douyin/scripts")

    profile = dict(env or {})
    if user_agent:
        profile["user_agent"] = user_agent
    if page_url:
        profile["page_url"] = page_url
        profile["referrer"] = page_url

    proc_env = os.environ.copy()
    proc_env["DOUYIN_BDM_PROFILE"] = json.dumps(profile, ensure_ascii=False, separators=(",", ":"))

    args = [
        "node",
        str(bdm_signer_path),
        full_url,
        "--drop-secsdk",
        "--bdm=bdm_live.js",
    ]
    if page_url:
        args.append(f"--page-url={page_url}")
    if user_agent:
        args.append(f"--ua={user_agent}")
    if data:
        args.append(f"--body={data}")

    try:
        result = subprocess.run(
            args,
            cwd=str(SCRIPTS_DIR),
            env=proc_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("未找到 Node.js，请先安装 Node.js，并在 backend 目录执行 npm ci 后重启后端") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("bdms 生成 a_bogus 超时，请稍后重试") from exc

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    if result.returncode != 0:
        detail = (stderr or stdout or "signer failed").strip()
        missing_module = _extract_missing_node_module(detail)
        if missing_module or "MODULE_NOT_FOUND" in detail:
            raise RuntimeError(_format_node_dependency_message(missing_module))
        raise RuntimeError(f"bdms 生成 a_bogus 失败: {detail[:500]}")

    signed_match = re.search(r"^signed_url\s*=\s*(.+)$", stdout, re.MULTILINE)
    signed_url = signed_match.group(1).strip() if signed_match else ""
    ab_match = re.search(r"^a_bogus\s*=\s*(.+)$", stdout, re.MULTILINE)
    a_bogus = ab_match.group(1).strip() if ab_match else ""
    if not a_bogus and signed_url:
        parsed = urllib.parse.urlparse(signed_url)
        values = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        a_bogus = (values.get("a_bogus") or [""])[0]

    if not signed_url or not a_bogus:
        raise RuntimeError("bdms 生成 a_bogus 失败: signer 输出缺少 signed_url 或 a_bogus")
    return {"signed_url": signed_url, "a_bogus": a_bogus}


def generate_bdm_signed_url(full_url, *, data="", user_agent=None, env=None, page_url=None, timeout=20):
    """使用当前 Web bdms SDK 补环境生成完整 signed_url。"""
    return _run_bdm_signer(
        full_url,
        data=data,
        user_agent=user_agent,
        env=env,
        page_url=page_url,
        timeout=timeout,
    )["signed_url"]


def generate_a_bogus_by_bdm(full_url, *, data="", user_agent=None, env=None, page_url=None, timeout=20):
    """使用当前 Web bdms SDK 补环境生成 a_bogus。

    这个路径用于抖音搜索类接口：a_bogus 不再调用旧的 p[42] 手工入口，
    而是让 bdms 在 Node VM 里通过 fetch hook 对完整 URL 签名。指纹信息
    必须从 Cookie/profile 动态传入，避免 UA、屏幕、平台等参数互相矛盾。
    """
    return _run_bdm_signer(
        full_url,
        data=data,
        user_agent=user_agent,
        env=env,
        page_url=page_url,
        timeout=timeout,
    )["a_bogus"]


# query, data都是拼接字符串
def generate_a_bogus(query, data="", user_agent=None, env=None, *, url=None, page_url=None, use_bdm=False):
    if use_bdm:
        if not url:
            raise ValueError("use_bdm=True 时必须传入完整接口 URL")
        separator = "&" if "?" in url else "?"
        full_url = f"{url}{separator}{query}" if query else url
        return generate_a_bogus_by_bdm(
            full_url,
            data=data,
            user_agent=user_agent or DEFAULT_DOUYIN_USER_AGENT,
            env=env or {},
            page_url=page_url,
        )
    if user_agent is None and env is None:
        return _call_js(_get_dy_js, 'get_ab', query, data)
    return _call_js(_get_dy_js, 'get_ab', query, data, user_agent or DEFAULT_DOUYIN_USER_AGENT, env or {})


def generate_signature(roomId, user_unique_id, webcast_sdk_version=DOUYIN_LIVE_WEBCAST_SDK_VERSION):
    raw_string = (
        "live_id=1,aid=6383,version_code=180800,"
        f"webcast_sdk_version={webcast_sdk_version},"
        f"room_id={roomId},sub_room_id=,sub_channel_id=,did_rule=3,"
        f"user_unique_id={user_unique_id},device_platform=web,device_type=,ac=,identity=audience"
    )
    x_ms_stub = hashlib.md5(raw_string.encode("utf-8")).hexdigest()
    return _call_js(_get_sign_js, 'get_signature', x_ms_stub)


# 传递私钥
def generate_ree_key(prik):
    ree_key = _call_js(_get_dy_js, 'get_ree_key', prik)
    return ree_key


# 传递query, ticket, ts_sign, priK
def generate_bd_ticket_client_data(api, ticket, ts_sign, priK):
    timestamp = int(time.time())
    res_sign = f"ticket={ticket}&path={api}&timestamp={timestamp}"
    p = {
        'ts_sign': ts_sign,
        'req_content': 'ticket,path,timestamp',
        'req_sign': generate_req_sign(res_sign, priK),
        'timestamp': timestamp,
    }
    p = json.dumps(p, ensure_ascii=False, separators=(',', ':'))
    return base64.urlsafe_b64encode(p.encode('utf-8')).decode('utf-8')


def generate_msToken(randomlength=107):
    random_str = ''
    base_str = 'ABCDEFGHIGKLMNOPQRSTUVWXYZabcdefghigklmnopqrstuvwxyz0123456789='
    length = len(base_str) - 1
    for _ in range(randomlength):
        random_str += base_str[random.randint(0, length)]
    return random_str


def generate_ttwid():
    url = f"https://www.douyin.com/discover?modal_id=7376449060384935209"
    ttwid = None
    try:
        headers = {
            'user-agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }
        response = requests.get(url, headers=headers, verify=False)
        cookies_dict = response.cookies.get_dict()
        ttwid = cookies_dict.get('ttwid')
        return ttwid
    except Exception as e:
        return ttwid


def generate_fake_webid(random_length=19):
    random_str = ''
    base_str = '0123456789'
    length = len(base_str) - 1
    for _ in range(random_length):
        random_str += base_str[random.randint(0, length)]
    return random_str


def generate_webid(auth=None, url=""):
    if url == "":
        url = f"https://www.douyin.com/discover?modal_id=7376449060384935209"
    try:
        from app.modules.douyin.common.header import HeaderBuilder, HeaderType
        headers = HeaderBuilder().build(HeaderType.DOC, auth=auth)
        headers.set_header('cookie', auth.cookie_str if auth else "")
        headers.set_header("upgrade-insecure-requests", "1")
        response = requests.get(url, headers=headers.get(), verify=False)
        header_webid = response.headers.get("Cookie_ttwidinfo_webid")
        if header_webid:
            return header_webid
        res_text = response.text
        user_unique_id = re.findall(r'\\"user_unique_id\\":\\"(.*?)\\"', res_text)[0]
        webid = user_unique_id
        return webid
    except Exception as e:
        return generate_fake_webid()


def ws_accept_key(ws_key):
    """calc the Sec-WebSocket-Accept key by Sec-WebSocket-key
    come from client, the return value used for handshake

    :ws_key: Sec-WebSocket-Key come from client
    :returns: Sec-WebSocket-Accept

    """
    import hashlib
    import base64
    try:
        magic = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
        sha1 = hashlib.sha1()
        sha1.update(ws_key + magic)
        return base64.b64encode(sha1.digest())
    except Exception as e:
        return None


def generate_csrf_token(cookies_str):
    csrf_token_1, csrf_token_2 = None, None
    try:
        headers = {
            'accept': '*/*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'cache-control': 'no-cache',
            'cookie': cookies_str,
            'pragma': 'no-cache',
            'priority': 'u=1, i',
            'referer': 'https://www.douyin.com/?recommend=1',
            'sec-ch-ua': '"Microsoft Edge";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            'x-secsdk-csrf-request': '1',
            'x-secsdk-csrf-version': '1.2.22',
        }
        response = requests.head('https://www.douyin.com/service/2/abtest_config/', headers=headers, verify=False)
        return response.headers['X-Ware-Csrf-Token'].split(',')[1], response.headers['X-Ware-Csrf-Token'].split(',')[4]
    except Exception as e:
        return csrf_token_1, csrf_token_2


def generate_millisecond():
    millis = int(round(time.time() * 1000))
    return millis


def splice_url(params):
    # a_bogus 必须基于最终发送的 query string 生成。requests/浏览器
    # URLSearchParams 对空值、中文、JSON、空格等会使用 form/urlencode 规则
    #（例如 "Mac OS" -> "Mac+OS"），这里不能用 quote 手拼，否则签名串与
    # 实际请求串不一致，容易触发 verify_check。
    normalized = {
        key: '' if value is None else str(value)
        for key, value in params.items()
    }
    return urllib.parse.urlencode(normalized)
