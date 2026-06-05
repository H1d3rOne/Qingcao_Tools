"""
依赖注入
"""
from functools import lru_cache
from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import get_db
from app.modules.douyin.video.spiders.douyin import DouyinSpider
from app.modules.base.schemas import ApiResponse
from app.modules.douyin.common.auth import DouyinAuth, auth
from app.modules.douyin.video.services.work_service import WorkService
from app.modules.douyin.video.services.user_service import UserService
from app.modules.douyin.video.services.search_service import SearchService
from app.modules.settings import SettingsService
from app.modules.quark.services.quark_service import QuarkService
from app.modules.wechat import WechatService
from app.modules.xianyu import XianyuService
from quark_client.cookie_store import load_quark_cookie_string
from xianyu_client.cookie_store import load_xianyu_cookie_string


DOUYIN_COOKIE_MISSING_MESSAGE = "抖音 Cookie 未配置，请先在设置页面配置抖音 Cookie"
QUARK_COOKIE_MISSING_MESSAGE = "夸克 Cookie 未配置，请先在设置页面配置夸克 Cookie"
XIANYU_COOKIE_MISSING_MESSAGE = "闲鱼 Cookie 未配置，请先在设置页面配置闲鱼 Cookie"


def _has_cookie_value(value: Optional[str]) -> bool:
    """判断配置中是否存在非空 Cookie。"""
    return bool((value or "").strip())


def is_douyin_cookie_configured() -> bool:
    """检查抖音视频/搜索/用户 Cookie 是否已配置。"""
    return _has_cookie_value(settings.DY_COOKIES)


def is_douyin_live_cookie_configured() -> bool:
    """检查抖音直播 Cookie 是否已配置；直播可复用普通抖音 Cookie。"""
    return _has_cookie_value(settings.DY_LIVE_COOKIES) or is_douyin_cookie_configured()


def get_quark_cookie_value() -> str:
    """获取当前可用的夸克 Cookie，优先读取专用存储文件。"""
    try:
        cookie_string = load_quark_cookie_string()
    except Exception as exc:
        logger.warning(f"读取夸克 Cookie 配置失败，已按未配置处理: {exc}")
        cookie_string = None
    if cookie_string:
        return cookie_string
    return (settings.QUARK_COOKIES or "").strip()


def is_quark_cookie_configured() -> bool:
    """检查夸克 Cookie 是否已配置。"""
    return _has_cookie_value(get_quark_cookie_value())


def get_xianyu_cookie_value() -> str:
    """获取当前可用的闲鱼 Cookie，优先读取专用存储文件。"""
    try:
        cookie_string = load_xianyu_cookie_string()
    except Exception as exc:
        logger.warning(f"读取闲鱼 Cookie 配置失败，已按未配置处理: {exc}")
        cookie_string = None
    if cookie_string:
        return cookie_string
    return (settings.XIANYU_COOKIES or "").strip()


def is_xianyu_cookie_configured() -> bool:
    """检查闲鱼 Cookie 是否已配置。"""
    return _has_cookie_value(get_xianyu_cookie_value())


def get_douyin_cookie_missing_response(*, live: bool = False) -> Optional[ApiResponse]:
    """返回统一的抖音 Cookie 未配置响应；已配置时返回 None。"""
    configured = is_douyin_live_cookie_configured() if live else is_douyin_cookie_configured()
    if configured:
        return None
    return ApiResponse(success=False, error=DOUYIN_COOKIE_MISSING_MESSAGE)


def require_quark_cookie() -> None:
    """需要夸克 Cookie 的接口前置校验。"""
    if not is_quark_cookie_configured():
        raise HTTPException(status_code=400, detail=QUARK_COOKIE_MISSING_MESSAGE)


def require_xianyu_cookie() -> None:
    """需要闲鱼 Cookie 的接口前置校验。"""
    if not is_xianyu_cookie_configured():
        raise HTTPException(status_code=400, detail=XIANYU_COOKIE_MISSING_MESSAGE)


@lru_cache()
def get_spider() -> DouyinSpider:
    """获取爬虫实例"""
    return DouyinSpider(auth)


def get_work_service(
    db: AsyncSession = Depends(get_db),
    spider: DouyinSpider = Depends(get_spider)
) -> WorkService:
    """获取作品服务"""
    return WorkService(db, spider)


def get_user_service(
    db: AsyncSession = Depends(get_db),
    spider: DouyinSpider = Depends(get_spider)
) -> UserService:
    """获取用户服务"""
    return UserService(db, spider)


def get_search_service(
    db: AsyncSession = Depends(get_db),
    spider: DouyinSpider = Depends(get_spider)
) -> SearchService:
    """获取搜索服务"""
    return SearchService(db, spider)


def get_settings_service() -> SettingsService:
    """获取设置服务"""
    return SettingsService()


def get_quark_service() -> QuarkService:
    """获取夸克服务"""
    return QuarkService()


@lru_cache()
def get_wechat_service() -> WechatService:
    """获取视频号下载服务"""
    return WechatService()


@lru_cache()
def get_xianyu_service() -> XianyuService:
    """获取闲鱼服务"""
    return XianyuService()


def get_current_auth() -> "DouyinAuth":
    """获取当前认证信息"""
    return auth


def get_current_live_auth() -> DouyinAuth:
    """获取直播认证信息，优先使用专用直播 Cookie。"""
    live_cookie = (settings.DY_LIVE_COOKIES or "").strip()
    if not live_cookie:
        return auth

    live_auth = DouyinAuth()
    live_auth.prepare_auth(live_cookie)
    return live_auth
