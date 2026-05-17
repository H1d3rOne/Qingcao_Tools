"""
抖音认证模块
"""
import json
import base64
import random
import string
from typing import Dict, Optional

from app.core.config import settings


class DouyinAuth:
    """抖音认证类"""
    
    def __init__(self):
        self.cookie: Dict[str, str] = {}
        self.cookie_str: str = ""
        self.private_key: Optional[str] = None
        self.ticket: Optional[str] = None
        self.ts_sign: Optional[str] = None
        self.client_cert: Optional[str] = None
        self.ree_public_key: Optional[str] = None
        self.uid: Optional[str] = None
        self.msToken: Optional[str] = None
        self.verifyFp: Optional[str] = None  # 添加 verifyFp 属性
        
        # 从配置初始化
        if settings.DY_COOKIES:
            self.prepare_auth(settings.DY_COOKIES)
    
    @staticmethod
    def _generate_s_v_web_id() -> str:
        """生成 s_v_web_id"""
        chars = string.ascii_letters + string.digits + '_'
        return 'verify_' + ''.join(random.choice(chars) for _ in range(18))
    
    @staticmethod
    def _generate_ms_token() -> str:
        """生成 msToken"""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(32))
    
    def _parse_cookies(self, cookie_str: str) -> Dict[str, str]:
        """解析 Cookie 字符串"""
        cookies = {}
        if cookie_str:
            for item in cookie_str.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies[key.strip()] = value.strip()
        return cookies
    
    def prepare_auth(self, cookie_str: str):
        """准备认证信息"""
        self.cookie = self._parse_cookies(cookie_str)
        self.cookie_str = cookie_str
        
        # 设置 msToken
        if "msToken" in self.cookie:
            self.msToken = self.cookie["msToken"]
        else:
            self.msToken = self._generate_ms_token()
            self.cookie["msToken"] = self.msToken
        
        # 设置 s_v_web_id 和 verifyFp
        if "s_v_web_id" in self.cookie and self.cookie["s_v_web_id"]:
            self.verifyFp = self.cookie["s_v_web_id"]
        else:
            self.verifyFp = self._generate_s_v_web_id()
            self.cookie["s_v_web_id"] = self.verifyFp
        
        # 重新生成 cookie_str
        self.cookie_str = "; ".join([f"{k}={v}" for k, v in self.cookie.items()])
    
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self.cookie_str)


# 全局认证实例
auth = DouyinAuth()
