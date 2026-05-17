"""
用户服务
"""
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.douyin.video.schemas.user import UserResponse
from app.modules.douyin.video.schemas.work import WorkResponse
from app.modules.douyin.video.spiders.douyin import DouyinSpider


class UserService:
    """用户服务"""
    
    def __init__(self, db: AsyncSession, spider: DouyinSpider):
        self.db = db
        self.spider = spider
    
    async def get_user_info(self, url: str) -> UserResponse:
        """获取用户信息"""
        user_data = await self.spider.get_user_info(url)
        return UserResponse(**user_data)
    
    async def get_user_info_by_sec_uid(self, sec_uid: str) -> UserResponse:
        """通过 sec_uid 获取用户信息"""
        user_data = await self.spider.get_user_info_by_sec_uid(sec_uid)
        return UserResponse(**user_data)
    
    async def get_user_works(self, url: str, limit: int = 20) -> List[WorkResponse]:
        """获取用户作品列表"""
        works = await self.spider.get_user_works(url, limit)
        return [WorkResponse(**w) for w in works]
    
    async def get_user_works_by_sec_uid(self, sec_uid: str, limit: int = 20, cursor: int = 0) -> List[WorkResponse]:
        """通过 sec_uid 获取用户作品列表"""
        works = await self.spider.get_user_works_by_sec_uid(sec_uid, limit, cursor)
        return [WorkResponse(**w) for w in works]
