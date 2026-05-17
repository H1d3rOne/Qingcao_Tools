"""
设置相关 Schema
"""
from pydantic import BaseModel, Field
from typing import Optional


class CookieInfo(BaseModel):
    """Cookie配置信息"""
    dy_configured: bool = Field(False, description="抖音Cookie是否已配置")
    dy_preview: str = Field("", description="抖音Cookie预览")
    live_configured: bool = Field(False, description="直播Cookie是否已配置")
    live_preview: str = Field("", description="直播Cookie预览")
    quark_configured: bool = Field(False, description="夸克Cookie是否已配置")
    quark_preview: str = Field("", description="夸克Cookie预览")
    xianyu_configured: bool = Field(False, description="闲鱼Cookie是否已配置")
    xianyu_preview: str = Field("", description="闲鱼Cookie预览")


class XianyuCookieValue(BaseModel):
    """闲鱼完整 Cookie"""
    configured: bool = Field(False, description="是否已配置闲鱼 Cookie")
    cookie: str = Field("", description="完整闲鱼 Cookie 字符串")


class UpdateDyCookieRequest(BaseModel):
    """更新抖音Cookie请求"""
    cookie: str = Field(..., description="抖音Cookie")


class UpdateLiveCookieRequest(BaseModel):
    """更新直播Cookie请求"""
    cookie: str = Field(..., description="直播Cookie")


class UpdateQuarkCookieRequest(BaseModel):
    """更新夸克Cookie请求"""
    cookie: str = Field(..., description="夸克Cookie")


class UpdateXianyuCookieRequest(BaseModel):
    """更新闲鱼Cookie请求"""
    cookie: str = Field(..., description="闲鱼Cookie")


class StatusResponse(BaseModel):
    """服务状态响应"""
    cookie_configured: bool = Field(False, description="抖音Cookie是否已配置")
    live_cookie_configured: bool = Field(False, description="直播Cookie是否已配置")
    quark_cookie_configured: bool = Field(False, description="夸克Cookie是否已配置")
    xianyu_cookie_configured: bool = Field(False, description="闲鱼Cookie是否已配置")
    message: str = Field("服务运行正常", description="状态消息")
