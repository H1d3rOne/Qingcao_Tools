from __future__ import annotations

import base64
import json
import random
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

from xianyu_client.config import get_config_dir


XIANYU_FINGERPRINT_FILE_NAME = "xianyu_fingerprint.json"


class XianyuAPILogin:
    def __init__(
        self,
        timeout: int = 300,
        fingerprint: Optional[Dict[str, Any]] = None,
        config_dir: Optional[Path] = None,
    ):
        self.timeout = timeout
        self.passport_base = "https://passport.goofish.com"
        self.config_dir = config_dir or get_config_dir()
        self.client = requests.Session()
        self.client.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/134.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.passport_base,
                "Referer": f"{self.passport_base}/mini_login.htm?lang=zh_cn&appName=xianyu&appEntrance=web",
            }
        )
        self._csrf_token = ""
        self._cna = ""
        self._active_qr: dict[str, str] | None = None
        self._poll_count = 0
        self.fingerprint: Dict[str, Any] = fingerprint if fingerprint is not None else self.load_fingerprint()

    def load_fingerprint(self, path: Optional[Path] = None) -> Dict[str, Any]:
        fingerprint_path = path or (self.config_dir / XIANYU_FINGERPRINT_FILE_NAME)
        if not fingerprint_path.exists():
            return {}

        try:
            return json.loads(fingerprint_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _current_poll_fingerprint(self) -> Dict[str, Any]:
        sequence = self.fingerprint.get("dynamic_fingerprints") or []
        if not sequence:
            return self.fingerprint

        idx = min(self._poll_count, len(sequence) - 1)
        self._poll_count += 1

        merged = dict(self.fingerprint)
        merged.update(sequence[idx])
        return merged

    @staticmethod
    def _generate_cna() -> str:
        raw = bytes(random.randint(0, 255) for _ in range(12))
        b64 = base64.b64encode(raw).decode("ascii").rstrip("=")
        return b64[:22] + "+" + b64[22:26]

    def _ensure_cna(self) -> str:
        if self._cna:
            return self._cna

        for domain in (".goofish.com", None):
            cna = self.client.cookies.get("cna", domain=domain)
            if cna:
                self._cna = cna
                return cna

        if self.fingerprint.get("deviceId"):
            self._cna = str(self.fingerprint["deviceId"])
            self.client.cookies.set("cna", self._cna, domain=".goofish.com")
            return self._cna

        self._cna = self._generate_cna()
        self.client.cookies.set("cna", self._cna, domain=".goofish.com")
        return self._cna

    def init_login_page(self) -> Dict[str, Any]:
        url = (
            f"{self.passport_base}/mini_login.htm"
            "?lang=zh_cn&appName=xianyu&appEntrance=web"
            "&styleType=vertical&bizParams=&notLoadSsoView=false"
            "&notKeepLogin=false&isMobile=false&qrCodeFirst=false&stie=77"
        )
        resp = self.client.get(url, timeout=15)
        resp.raise_for_status()

        for domain in (".goofish.com", None):
            csrf_token = self.client.cookies.get("XSRF-TOKEN", domain=domain)
            if csrf_token:
                self._csrf_token = csrf_token
                break

        if self.fingerprint.get("csrf_token"):
            self._csrf_token = str(self.fingerprint["csrf_token"])

        self._ensure_cna()
        return {"status": resp.status_code, "cookies": list(self.client.cookies.keys())}

    def get_qr_code(self) -> Tuple[str, str]:
        if not self._csrf_token and not self.client.cookies:
            self.init_login_page()

        self._ensure_cna()
        qr_token = self._generate_qr_token()
        qr_url = self._build_qr_url(qr_token)
        self._active_qr = {"token": qr_token, "url": qr_url}
        return qr_token, qr_url

    def query_qrcode(self, t: str, device_id: str, page_trace_id: str) -> Dict[str, Any]:
        url = f"{self.passport_base}/newlogin/qrcode/query.do?appName=xianyu&fromSite=77"
        poll_fingerprint = self._current_poll_fingerprint()
        ck = str(poll_fingerprint.get("ck") or self.client.cookies.get("cookie2", ""))
        csrf_token = str(poll_fingerprint.get("csrf_token") or self._csrf_token)
        umid_token = str(poll_fingerprint.get("umidToken") or "")
        nav_user_agent = str(
            poll_fingerprint.get("navUserAgent")
            or self.client.headers.get("User-Agent", "")
        )
        resolved_device_id = str(device_id or poll_fingerprint.get("deviceId") or self._ensure_cna())

        data = {
            "t": t,
            "ck": ck,
            "appName": "xianyu",
            "appEntrance": "web",
            "_csrf_token": csrf_token,
            "umidToken": umid_token,
            "hsiz": ck,
            "bizParams": "taobaoBizLoginFrom=web&renderRefer=https%3A%2F%2Fwww.goofish.com%2F",
            "mainPage": "false",
            "isMobile": "false",
            "lang": "zh_CN",
            "returnUrl": "",
            "fromSite": "77",
            "umidTag": "SERVER",
            "navlanguage": "zh-CN",
            "navUserAgent": nav_user_agent,
            "navPlatform": "MacIntel",
            "isIframe": "true",
            "documentReferer": "https://www.goofish.com/",
            "defaultView": "sms",
            "deviceId": resolved_device_id,
            "pageTraceId": page_trace_id,
        }

        if poll_fingerprint.get("ua"):
            data["ua"] = poll_fingerprint["ua"]
        if poll_fingerprint.get("bx_ua"):
            data["bx-ua"] = poll_fingerprint["bx_ua"]
        if poll_fingerprint.get("bx_umidtoken"):
            data["bx-umidtoken"] = poll_fingerprint["bx_umidtoken"]
        if poll_fingerprint.get("bx_et"):
            data["bx_et"] = poll_fingerprint["bx_et"]
        if poll_fingerprint.get("x_pipu2"):
            data["x-pipu2"] = poll_fingerprint["x_pipu2"]

        resp = self.client.post(url, data=data, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def confirm_login(self, token: str, device_id: str, page_trace_id: str) -> Dict[str, Any]:
        url = (
            f"{self.passport_base}/login_token/login.do"
            f"?token={token}&subFlow=DIALOG_CHECK_LOGIN_RPC"
            f"&nextCode=0018&bizScene=qrcode&confirm=true"
        )
        resp = self.client.post(
            url,
            data={"deviceId": device_id, "pageTraceId": page_trace_id},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def query_login_settings(self) -> Dict[str, Any]:
        url = f"{self.passport_base}/ac/account/queryLoginSettings.do?fromSite=77&appName=xianyu&bizEntrance=web"
        resp = self.client.post(url, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def silent_has_login(self) -> Dict[str, Any]:
        url = (
            f"{self.passport_base}/newlogin/silentHasLogin.do"
            "?documentReferer=https%3A%2F%2Fwww.goofish.com%2F"
            "&appName=xianyu&appEntrance=xianyu_sdkSilent&fromSite=0&ltl=true"
        )
        resp = self.client.post(url, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        sdk_silent = result.get("content", {}).get("data", {}).get("sdkSilent", "")
        if sdk_silent:
            self.client.cookies.set("sdkSilent", sdk_silent, domain=".goofish.com")
        return result

    def extract_xianyu_cookie_string(self) -> str:
        cookies = []
        for cookie in self.client.cookies:
            if cookie.domain and "goofish.com" in cookie.domain:
                cookies.append(f"{cookie.name}={cookie.value}")
        return "; ".join(cookies)

    def _generate_qr_token(self) -> str:
        import time
        return str(int(time.time() * 1000))

    def _build_qr_url(self, token: str) -> str:
        return (
            "https://login.goofish.com/qr/login"
            f"?t={token}&fromSite=77&appName=xianyu&appEntrance=web"
        )

    def _generate_page_trace_id(self) -> str:
        import time
        return f"215041d9{int(time.time() * 1000000)}7ef93d"
