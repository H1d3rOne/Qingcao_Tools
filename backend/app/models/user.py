"""
用户数据模型
"""
from sqlalchemy import Column, String, Text, Integer, BigInteger
from sqlalchemy import Index

from app.models.base import BaseModel


class User(BaseModel):
    """用户模型"""
    __tablename__ = "users"
    
    uid = Column(String(50), unique=True, index=True, nullable=False, comment="用户UID")
    sec_uid = Column(String(200), unique=True, index=True, comment="sec_uid")
    unique_id = Column(String(100), comment="抖音号")
    
    # 基本信息
    nickname = Column(String(100), comment="昵称")
    signature = Column(Text, comment="签名")
    avatar = Column(String(500), comment="头像")
    
    # 统计信息
    follower_count = Column(Integer, default=0, comment="粉丝数")
    following_count = Column(Integer, default=0, comment="关注数")
    aweme_count = Column(Integer, default=0, comment="作品数")
    favoriting_count = Column(Integer, default=0, comment="喜欢数")
    
    # 索引
    __table_args__ = (
        Index('idx_uid_sec_uid', 'uid', 'sec_uid'),
    )
