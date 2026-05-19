"""
设置相关 API
"""
from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.base.schemas import ApiResponse
from app.modules.settings import (
    CookieInfo, UpdateDyCookieRequest,
    UpdateLiveCookieRequest, UpdateQuarkCookieRequest,
    UpdateXianyuCookieRequest, StatusResponse, XianyuCookieValue
)
from app.modules.settings import SettingsService
from app.api.deps import get_settings_service, get_xianyu_service
from app.db.database import get_db
from app.modules.douyin.video.services.stats_service import StatsService

router = APIRouter(prefix="/settings", tags=["设置"])


@router.get("/status", response_model=ApiResponse[StatusResponse])
async def get_status(
    service: SettingsService = Depends(get_settings_service)
):
    """获取服务状态"""
    status = await service.get_status()
    return ApiResponse(data=status)


@router.get("/cookie", response_model=ApiResponse[CookieInfo])
async def get_cookie_settings(
    service: SettingsService = Depends(get_settings_service)
):
    """获取 Cookie 配置"""
    cookie_info = await service.get_cookie_settings()
    return ApiResponse(data=cookie_info)


@router.get("/cookie/xianyu/full", response_model=ApiResponse[XianyuCookieValue])
async def get_xianyu_full_cookie(
    service: SettingsService = Depends(get_settings_service)
):
    """获取闲鱼完整 Cookie，供登录页手动填充输入框。"""
    return ApiResponse(data=await service.get_xianyu_cookie_value())


@router.post("/cookie/dy", response_model=ApiResponse)
async def update_dy_cookie(
    request: UpdateDyCookieRequest,
    service: SettingsService = Depends(get_settings_service)
):
    """更新抖音 Cookie"""
    success = await service.update_dy_cookie(request.cookie)
    if success:
        return ApiResponse(message="抖音Cookie更新成功")
    return ApiResponse(success=False, error="更新失败")


@router.post("/cookie/live", response_model=ApiResponse)
async def update_live_cookie(
    request: UpdateLiveCookieRequest,
    service: SettingsService = Depends(get_settings_service)
):
    """更新直播 Cookie"""
    success = await service.update_live_cookie(request.cookie)
    if success:
        return ApiResponse(message="直播Cookie更新成功")
    return ApiResponse(success=False, error="更新失败")


@router.post("/cookie/quark", response_model=ApiResponse)
async def update_quark_cookie(
    request: UpdateQuarkCookieRequest,
    service: SettingsService = Depends(get_settings_service)
):
    """更新夸克 Cookie"""
    success = await service.update_quark_cookie(request.cookie)
    if success:
        return ApiResponse(message="夸克Cookie更新成功")
    return ApiResponse(success=False, error="更新失败")


@router.post("/cookie/xianyu", response_model=ApiResponse)
async def update_xianyu_cookie(
    request: UpdateXianyuCookieRequest,
    service: SettingsService = Depends(get_settings_service)
):
    """更新闲鱼 Cookie"""
    success = await service.update_xianyu_cookie(request.cookie)
    if success:
        # 通知闲鱼服务重置共享 ws 并用新 cookie 重启 listener / 保活
        try:
            xianyu_service = get_xianyu_service()
            await xianyu_service.on_xianyu_cookie_updated()
        except Exception as exc:
            logger.warning(f"Cookie 更新后重启闲鱼后台监听失败: {exc}")
        return ApiResponse(message="闲鱼Cookie更新成功")
    return ApiResponse(success=False, error="更新失败")


@router.get("/stats", response_model=ApiResponse)
async def get_usage_stats(
    db: AsyncSession = Depends(get_db)
):
    """获取使用统计"""
    service = StatsService(db)
    stats = await service.get_stats()
    return ApiResponse(data=stats)
