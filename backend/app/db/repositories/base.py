"""
基础仓储类
"""
from typing import TypeVar, Generic, Type, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """基础仓储类"""
    
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def create(self, obj: ModelType) -> ModelType:
        """创建记录"""
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj
    
    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """通过ID获取"""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """获取所有记录"""
        result = await self.session.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    async def update(self, id: int, **kwargs) -> Optional[ModelType]:
        """更新记录"""
        obj = await self.get_by_id(id)
        if obj:
            for key, value in kwargs.items():
                setattr(obj, key, value)
            await self.session.flush()
            await self.session.refresh(obj)
        return obj
    
    async def delete(self, id: int) -> bool:
        """删除记录"""
        obj = await self.get_by_id(id)
        if obj:
            await self.session.delete(obj)
            return True
        return False
