"""
作品数据模型
"""
from sqlalchemy import Column, String, Text, Integer, BigInteger, Boolean
from sqlalchemy import Index

from app.models.base import BaseModel


class Work(BaseModel):
    """作品模型"""
    __tablename__ = "works"
    
    aweme_id = Column(String(50), unique=True, index=True, nullable=False, comment="作品ID")
    title = Column(String(500), comment="标题")
    desc = Column(Text, comment="描述")
    author_uid = Column(String(50), index=True, comment="作者UID")
    author_nickname = Column(String(100), comment="作者昵称")
    author_avatar = Column(String(500), comment="作者头像")
    author_sec_uid = Column(String(200), comment="作者sec_uid")
    
    # 媒体信息
    cover_url = Column(String(500), comment="封面URL")
    video_url = Column(String(500), comment="视频URL")
    images = Column(Text, comment="图片列表JSON")
    duration = Column(Integer, default=0, comment="时长(毫秒)")
    music_title = Column(String(200), comment="音乐标题")
    
    # 统计信息
    digg_count = Column(Integer, default=0, comment="点赞数")
    comment_count = Column(Integer, default=0, comment="评论数")
    share_count = Column(Integer, default=0, comment="分享数")
    collect_count = Column(Integer, default=0, comment="收藏数")
    play_count = Column(Integer, default=0, comment="播放数")
    
    # 其他属性
    is_video = Column(Boolean, default=True, comment="是否视频")
    create_time = Column(BigInteger, comment="创建时间戳")
    work_url = Column(String(500), comment="原始链接")
    
    # 联合索引
    __table_args__ = (
        Index('idx_author_create', 'author_uid', 'create_time'),
    )
