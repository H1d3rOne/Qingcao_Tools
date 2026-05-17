"""
基础数据模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.sql import func

from app.db.database import Base


class BaseModel(Base):
    """基础模型抽象类"""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
