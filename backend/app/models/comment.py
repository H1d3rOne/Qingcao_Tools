"""
评论数据模型
"""
from sqlalchemy import Column, String, Text, Integer, BigInteger, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Comment(BaseModel):
    """评论模型"""
    __tablename__ = "comments"
    
    cid = Column(String(50), unique=True, index=True, nullable=False, comment="评论ID")
    aweme_id = Column(String(50), index=True, nullable=False, comment="作品ID")
    
    # 评论内容
    text = Column(Text, comment="评论内容")
    digg_count = Column(Integer, default=0, comment="点赞数")
    
    # 用户信息
    user_uid = Column(String(50), index=True, comment="用户UID")
    user_nickname = Column(String(100), comment="用户昵称")
    user_avatar = Column(String(500), comment="用户头像")
    
    # 时间
    create_time = Column(BigInteger, comment="创建时间戳")
    
    # 回复
    reply_comment_id = Column(Integer, ForeignKey("comments.id"), comment="回复的评论ID")
