"""
用户相关 API
"""
from fastapi import APIRouter, Depends

from app.modules.base.schemas import ApiResponse
from app.modules.douyin.video.schemas.user import UserInfoRequest, UserWorksRequest, UserResponse
from app.modules.douyin.video.schemas.work import WorkResponse
from app.modules.douyin.video.services.user_service import UserService
from app.api.deps import get_user_service
from typing import List

router = APIRouter(prefix="/user", tags=["用户"])


@router.post("/info", response_model=ApiResponse[UserResponse])
async def get_user_info(
    request: UserInfoRequest,
    service: UserService = Depends(get_user_service)
):
    """获取用户信息"""
    try:
        # 支持 url 或 sec_uid 参数
        if request.url:
            user = await service.get_user_info(request.url)
        elif request.sec_uid:
            user = await service.get_user_info_by_sec_uid(request.sec_uid)
        else:
            return ApiResponse(success=False, error="请提供 url 或 sec_uid 参数")
        return ApiResponse(data=user)
    except Exception as e:
        return ApiResponse(success=False, error=str(e))


@router.post("/works", response_model=ApiResponse[List[WorkResponse]])
async def get_user_works(
    request: UserWorksRequest,
    service: UserService = Depends(get_user_service)
):
    """获取用户作品列表"""
    try:
        # 支持 url 或 sec_uid 参数
        if request.url:
            works = await service.get_user_works(request.url, request.limit or request.count or 20)
        elif request.sec_uid:
            works = await service.get_user_works_by_sec_uid(
                request.sec_uid, 
                request.count or request.limit or 20,
                request.cursor or 0
            )
        else:
            return ApiResponse(success=False, error="请提供 url 或 sec_uid 参数")
        return ApiResponse(data=works)
    except Exception as e:
        return ApiResponse(success=False, error=str(e))
