"""
作品相关 Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class VideoQuality(BaseModel):
    """视频质量"""
    quality_type: int = Field(..., description="质量类型: 24=标清, 10=高清, 1=超清, 7=2K")
    url: str = Field(..., description="视频URL")
    width: Optional[int] = Field(None, description="宽度")
    height: Optional[int] = Field(None, description="高度")


class WorkBase(BaseModel):
    """作品基础模式"""
    aweme_id: str = Field(..., description="作品ID")
    title: Optional[str] = Field(None, description="标题")
    desc: Optional[str] = Field(None, description="描述")
    author_uid: Optional[str] = Field(None, description="作者UID")
    author_nickname: Optional[str] = Field(None, description="作者昵称")
    author_avatar: Optional[str] = Field(None, description="作者头像")
    cover_url: Optional[str] = Field(None, description="封面URL")
    video_url: Optional[str] = Field(None, description="视频URL(默认超清)")
    video_qualities: Optional[Dict[str, VideoQuality]] = Field(None, description="不同质量的视频链接")
    duration: int = Field(0, description="时长(毫秒)")
    digg_count: int = Field(0, description="点赞数")
    comment_count: int = Field(0, description="评论数")
    share_count: int = Field(0, description="分享数")
    collect_count: int = Field(0, description="收藏数")
    play_count: int = Field(0, description="播放数")
    is_video: bool = Field(True, description="是否视频")


class WorkCreate(WorkBase):
    """创建作品"""
    images: Optional[List[str]] = None
    music_title: Optional[str] = None
    create_time: Optional[int] = None
    work_url: Optional[str] = None


class WorkResponse(WorkBase):
    """作品响应"""
    id: Optional[int] = None
    author_sec_uid: Optional[str] = None
    images: Optional[List[str]] = None
    music_title: Optional[str] = None
    create_time: Optional[int] = None
    work_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class WorkInfoRequest(BaseModel):
    """获取作品信息请求"""
    url: Optional[str] = Field(None, description="作品链接")
    aweme_id: Optional[str] = Field(None, description="作品ID")


class WorkCommentsRequest(BaseModel):
    """获取作品评论请求"""
    url: Optional[str] = Field(None, description="作品链接")
    aweme_id: Optional[str] = Field(None, description="作品ID")
    cursor: Optional[int] = Field(0, description="分页游标")
    limit: int = Field(20, ge=1, le=100, description="获取数量")
    count: Optional[int] = Field(20, ge=1, le=100, description="获取数量(兼容)")


class WorkDownloadRequest(BaseModel):
    """下载作品请求"""
    url: Optional[str] = Field(None, description="作品链接")
    aweme_id: Optional[str] = Field(None, description="作品ID")
    save_type: str = Field("media", description="保存类型: media/video/image")
    quality: str = Field("super", description="视频质量: standard=标清, high=高清, super=超清, hd2k=2K")


class DownloadResult(BaseModel):
    """下载结果"""
    title: str
    author: str
    aweme_id: str
    video_url: Optional[str] = None
    video_qualities: Optional[Dict[str, Any]] = None
    images: Optional[List[str]] = None
    filename: Optional[str] = None
    selected_quality: Optional[str] = None
