from fastapi import APIRouter, HTTPException
from typing import Optional

from app.modules.quark.schemas import (
    LoginRequest,
    LoginResponse,
    AuthStatusResponse,
    LogoutResponse,
    QRCodeResponse,
    CheckLoginRequest,
    CheckLoginResponse,
)
from app.modules.quark.services import quark_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.get("/qrcode", response_model=QRCodeResponse)
async def get_qrcode():
    """
    获取登录二维码（非阻塞）
    
    返回二维码URL和token，前端需要轮询 /auth/check-login 来检查登录状态
    """
    result = quark_service.get_qrcode()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return QRCodeResponse(
        success=result["success"],
        message=result["message"],
        qrcode_url=result.get("qrcode_url"),
        qrcode_token=result.get("qrcode_token"),
        qrcode_image=result.get("qrcode_image"),
    )


@router.post("/check-login", response_model=CheckLoginResponse)
async def check_login_status(request: CheckLoginRequest):
    """
    检查登录状态
    
    前端轮询此接口检查用户是否已扫码登录
    """
    result = quark_service.check_login_status(request.qrcode_token)
    
    return CheckLoginResponse(
        success=result["success"],
        message=result["message"],
        is_logged_in=result.get("is_logged_in", False),
        login_token=result.get("login_token"),
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    登录夸克网盘
    
    - method: 登录方式 (api=二维码登录, simple=Cookie登录)
    - cookies: Cookie 字符串 (simple 方式时需要)
    
    注意：推荐使用 GET /auth/qrcode + POST /auth/check-login 进行二维码登录
    """
    result = quark_service.login(method=request.method, cookies=request.cookies)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return LoginResponse(
        success=result["success"],
        message=result["message"],
        qrcode_url=result.get("qrcode_url"),
        login_token=result.get("cookies"),
    )


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status():
    """获取当前登录状态"""
    is_logged_in = quark_service.is_logged_in()

    user_info = None
    if is_logged_in:
        try:
            user_result = quark_service.get_user_info()
            if user_result.get("success"):
                user_info = user_result.get("data")
        except Exception:
            pass

    return AuthStatusResponse(
        is_logged_in=is_logged_in,
        user_info=user_info,
    )


@router.post("/auto-login", response_model=LoginResponse)
async def auto_login():
    """
    尝试使用已保存的 Cookie 自动登录
    
    检查本地是否有有效的 Cookie，如果有则自动登录
    """
    result = quark_service.try_auto_login()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return LoginResponse(
        success=result["success"],
        message=result["message"],
        login_token=result.get("cookies"),
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout():
    """登出"""
    result = quark_service.logout()
    
    return LogoutResponse(
        success=result["success"],
        message=result["message"],
    )
