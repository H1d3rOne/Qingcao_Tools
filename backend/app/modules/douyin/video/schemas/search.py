"""
搜索相关 Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from .work import WorkResponse


class SearchWorkRequest(BaseModel):
    """搜索作品请求"""
    keyword: str = Field(..., description="搜索关键词")
    limit: int = Field(20, ge=1, le=100, description="获取数量")
    sort_type: str = Field("0", description="排序: 0综合, 1最多点赞, 2最新")
    publish_time: str = Field("0", description="发布时间: 0不限, 1一天内, 7一周内, 180半年内")
    filter_duration: str = Field("", description="视频时长: 空/不限, 0-1一分钟内, 1-5一分钟到五分钟, 5-10000五分钟以上")
    content_type: str = Field("", description="内容形式: 0不限, 1视频, 2图文")


class SearchVideoRequest(BaseModel):
    """搜索视频请求"""
    keyword: str = Field(..., description="搜索关键词")
    limit: int = Field(20, ge=1, le=100, description="获取数量")
    sort_type: str = Field("0", description="排序: 0综合, 1最多点赞, 2最新")
    publish_time: str = Field("0", description="发布时间: 0不限, 1一天内, 7一周内, 180半年内")
    filter_duration: str = Field("", description="视频时长: 空/不限, 0-1一分钟内, 1-5一分钟到五分钟, 5-10000五分钟以上")
    search_range: str = Field("0", description="搜索范围: 0不限, 1最近看过, 2还未看过, 3关注的人")


class SearchUserRequest(BaseModel):
    """搜索用户请求"""
    keyword: str = Field(..., description="搜索关键词")
    limit: int = Field(20, ge=1, le=100, description="获取数量")


class SearchLiveRequest(BaseModel):
    """搜索直播请求"""
    keyword: str = Field(..., description="搜索关键词")
    limit: int = Field(20, ge=1, le=100, description="获取数量")


class SearchResult(BaseModel):
    """搜索结果"""
    keyword: str
    total: int
    items: List[dict]
