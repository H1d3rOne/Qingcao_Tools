"""
依赖注入
"""
from functools import lru_cache
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.modules.douyin.video.spiders.douyin import DouyinSpider
from app.modules.douyin.common.auth import auth
from app.modules.douyin.video.services.work_service import WorkService
from app.modules.douyin.video.services.user_service import UserService
from app.modules.douyin.video.services.search_service import SearchService
from app.modules.settings import SettingsService
from app.modules.quark.services.quark_service import QuarkService
from app.modules.wechat import WechatService
from app.modules.xianyu import XianyuService


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
