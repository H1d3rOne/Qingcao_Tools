from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    """登录请求"""
    method: str = Field(default="api", description="登录方式: api, simple")
    cookies: Optional[str] = Field(default=None, description="Cookie 字符串 (simple 方式时需要)")


class LoginResponse(BaseModel):
    """登录响应"""
    success: bool
    message: str
    qrcode_url: Optional[str] = None
    login_token: Optional[str] = None


class QRCodeResponse(BaseModel):
    """二维码响应"""
    success: bool
    message: str
    qrcode_url: Optional[str] = None
    qrcode_token: Optional[str] = None
    qrcode_image: Optional[str] = None


class CheckLoginRequest(BaseModel):
    """检查登录状态请求"""
    qrcode_token: str = Field(..., description="二维码token")


class CheckLoginResponse(BaseModel):
    """检查登录状态响应"""
    success: bool
    message: str
    is_logged_in: bool = False
    login_token: Optional[str] = None


class AuthStatusResponse(BaseModel):
    """认证状态响应"""
    is_logged_in: bool
    user_info: Optional[dict] = None


class LogoutResponse(BaseModel):
    """登出响应"""
    success: bool
    message: str
