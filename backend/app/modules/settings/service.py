"""
设置服务
"""
import yaml
from app.core.config import settings as app_settings, _find_config_file
from app.core.config_bootstrap import backup_runtime_file
from app.modules.settings.schemas import CookieInfo, StatusResponse, XianyuCookieValue
from app.modules.douyin.common.auth import auth
from quark_client.cookie_store import load_quark_cookie_string, save_quark_cookie_string
from xianyu_client.cookie_store import (
    load_xianyu_cookie_string,
    normalize_xianyu_cookie_input,
    save_xianyu_cookie_string,
)


class SettingsService:
    """设置服务"""
    
    def __init__(self):
        self.config_path = _find_config_file()
    
    async def get_status(self) -> StatusResponse:
        """获取服务状态"""
        return StatusResponse(
            cookie_configured=bool(app_settings.cookies.douyin),
            live_cookie_configured=bool(app_settings.cookies.douyin_live),
            quark_cookie_configured=bool(self._get_quark_cookie_value()),
            xianyu_cookie_configured=bool(self._get_xianyu_cookie_value()),
            message="服务运行正常"
        )
    
    async def get_cookie_settings(self) -> CookieInfo:
        """获取 Cookie 配置"""
        return CookieInfo(
            dy_configured=bool(app_settings.cookies.douyin),
            dy_preview=self._get_preview(app_settings.cookies.douyin),
            live_configured=bool(app_settings.cookies.douyin_live),
            live_preview=self._get_preview(app_settings.cookies.douyin_live),
            quark_configured=bool(self._get_quark_cookie_value()),
            quark_preview=self._get_preview(self._get_quark_cookie_value()),
            xianyu_configured=bool(self._get_xianyu_cookie_value()),
            xianyu_preview=self._get_preview(self._get_xianyu_cookie_value())
        )

    async def get_xianyu_cookie_value(self) -> XianyuCookieValue:
        """获取闲鱼完整 Cookie 字符串。"""
        cookie = self._get_xianyu_cookie_value()
        return XianyuCookieValue(
            configured=bool(cookie),
            cookie=cookie,
        )
    
    def _get_preview(self, value: str, length: int = 50) -> str:
        """获取预览字符串"""
        if not value:
            return ""
        return value[:length] + "..." if len(value) > length else value
    
    async def update_dy_cookie(self, cookie: str) -> bool:
        """更新抖音 Cookie"""
        cleaned = self._clean_cookie_string(cookie)
        success = await self._update_config("cookies", "douyin", cleaned)
        if success:
            auth.prepare_auth(cleaned)
        return success
    
    async def update_live_cookie(self, cookie: str) -> bool:
        """更新直播 Cookie"""
        cleaned = self._clean_cookie_string(cookie)
        return await self._update_config("cookies", "douyin_live", cleaned)
    
    async def update_quark_cookie(self, cookie: str) -> bool:
        """更新夸克 Cookie"""
        try:
            cleaned = self._clean_cookie_string(cookie)
            save_quark_cookie_string(cleaned, source="settings_input")
            return True
        except Exception as e:
            print(f"更新夸克配置失败: {e}")
            return False

    async def update_xianyu_cookie(self, cookie: str) -> bool:
        """更新闲鱼 Cookie"""
        try:
            cleaned = normalize_xianyu_cookie_input(cookie)
            save_xianyu_cookie_string(cleaned, source="settings_input")
            app_settings.cookies.xianyu = cleaned
            return True
        except Exception as e:
            print(f"更新闲鱼配置失败: {e}")
            return False

    def _clean_cookie_string(self, cookie: str) -> str:
        """清理 Cookie 字符串中的非法字符"""
        if not cookie:
            return ""
        cleaned = cookie.strip()
        cleaned = cleaned.replace("\n", "").replace("\r", "").replace("\t", " ")
        while "  " in cleaned:
            cleaned = cleaned.replace("  ", " ")
        return cleaned
    
    async def _update_config(self, section: str, key: str, value: str) -> bool:
        """更新 YAML 配置文件"""
        try:
            # 读取现有配置
            config_data = {}
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config_data = yaml.safe_load(f) or {}
            
            # 确保节存在
            if section not in config_data:
                config_data[section] = {}
            
            # 更新配置值
            config_data[section][key] = value
            
            # 写回文件
            backup_runtime_file(self.config_path)
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            backup_runtime_file(self.config_path)
            
            # 更新内存中的配置
            if section == "cookies":
                if key == "douyin":
                    app_settings.cookies.douyin = value
                elif key == "douyin_live":
                    app_settings.cookies.douyin_live = value
                elif key == "quark":
                    app_settings.cookies.quark = value
                elif key == "xianyu":
                    app_settings.cookies.xianyu = value
            
            return True
        except Exception as e:
            print(f"更新配置失败: {e}")
            return False

    def _get_quark_cookie_value(self) -> str:
        """获取夸克 Cookie，优先读取专用存储文件。"""
        cookie_string = load_quark_cookie_string()
        if cookie_string:
            return cookie_string
        return (app_settings.cookies.quark or "").strip()

    def _get_xianyu_cookie_value(self) -> str:
        """获取闲鱼 Cookie，优先读取专用存储文件。"""
        cookie_string = load_xianyu_cookie_string()
        if cookie_string:
            return cookie_string
        return (app_settings.cookies.xianyu or "").strip()
