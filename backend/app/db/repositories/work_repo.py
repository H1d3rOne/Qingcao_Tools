"""
作品仓储类
"""
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.work import Work


class WorkRepository(BaseRepository[Work]):
    """作品仓储"""
    
    def __init__(self, session: AsyncSession):
        super().__init__(Work, session)
    
    async def get_by_aweme_id(self, aweme_id: str) -> Optional[Work]:
        """通过作品ID获取"""
        result = await self.session.execute(
            select(Work).where(Work.aweme_id == aweme_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_author(self, author_uid: str, limit: int = 20) -> List[Work]:
        """获取作者的作品列表"""
        result = await self.session.execute(
            select(Work)
            .where(Work.author_uid == author_uid)
            .order_by(Work.create_time.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def create_or_update(self, work_data: dict) -> Work:
        """创建或更新作品"""
        existing = await self.get_by_aweme_id(work_data["aweme_id"])
        if existing:
            for key, value in work_data.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        else:
            work = Work(**work_data)
            return await self.create(work)
