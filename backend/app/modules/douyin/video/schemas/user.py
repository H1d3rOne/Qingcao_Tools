"""
用户相关 Schema
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """用户基础模式"""
    uid: str = Field(..., description="用户UID")
    sec_uid: Optional[str] = Field(None, description="sec_uid")
    unique_id: Optional[str] = Field(None, description="抖音号")
    nickname: Optional[str] = Field(None, description="昵称")
    signature: Optional[str] = Field(None, description="签名")
    avatar: Optional[str] = Field(None, description="头像URL")
    follower_count: int = Field(0, description="粉丝数")
    following_count: int = Field(0, description="关注数")
    aweme_count: int = Field(0, description="作品数")
    favoriting_count: Optional[int] = Field(None, description="喜欢数")


class UserResponse(UserBase):
    """用户响应"""
    id: Optional[int] = Field(None, description="用户ID")
    uid: Optional[str] = Field(None, description="用户UID")
    sec_uid: Optional[str] = Field(None, description="sec_uid")
    unique_id: Optional[str] = Field(None, description="抖音号")
    nickname: Optional[str] = Field(None, description="昵称")
    signature: Optional[str] = Field(None, description="签名")
    avatar: Optional[str] = Field(None, description="头像URL")
    gender: Optional[int] = Field(None, description="性别：1-男，2-女")
    user_age: Optional[int] = Field(None, description="用户年龄")
    ip_location: Optional[str] = Field(None, description="IP位置")
    country: Optional[str] = Field(None, description="国家/地区")
    follower_count: int = Field(0, description="粉丝数")
    following_count: int = Field(0, description="关注数")
    aweme_count: int = Field(0, description="作品数")
    favoriting_count: Optional[int] = Field(None, description="喜欢数")
    
    class Config:
        from_attributes = True


class UserInfoRequest(BaseModel):
    """获取用户信息请求"""
    url: Optional[str] = Field(None, description="用户主页链接")
    sec_uid: Optional[str] = Field(None, description="用户sec_uid")


class UserWorksRequest(BaseModel):
    """获取用户作品请求"""
    url: Optional[str] = Field(None, description="用户主页链接")
    sec_uid: Optional[str] = Field(None, description="用户sec_uid")
    cursor: Optional[int] = Field(0, description="分页游标")
    count: Optional[int] = Field(20, ge=1, le=100, description="获取数量")
    limit: Optional[int] = Field(20, ge=1, le=100, description="获取数量(兼容)")
