"""
搜索相关 API
"""
from fastapi import APIRouter, Depends
from loguru import logger

from app.modules.base.schemas import ApiResponse
from app.modules.douyin.video.schemas.search import (
    SearchWorkRequest, SearchVideoRequest, SearchUserRequest, SearchLiveRequest, SearchPageResult
)
from app.modules.douyin.video.services.search_service import SearchService
from app.api.deps import get_search_service
from app.modules.douyin.common.auth import auth

router = APIRouter(prefix="/search", tags=["搜索"])


@router.post("/work", response_model=ApiResponse[SearchPageResult])
async def search_works(
    request: SearchWorkRequest,
    service: SearchService = Depends(get_search_service)
):
    """搜索作品"""
    try:
        logger.info(f"搜索作品: keyword={request.keyword}, offset={request.offset}, count={request.count}")
        result = await service.search_works(
            request.keyword,
            request.offset,
            request.count,
            request.search_id,
            request.sort_type,
            request.publish_time,
            request.filter_duration,
            request.search_range,
            request.content_type,
        )
        return ApiResponse(data=result)
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        import traceback
        traceback.print_exc()
        return ApiResponse(success=False, error=str(e))


@router.post("/video", response_model=ApiResponse[SearchPageResult])
async def search_videos(
    request: SearchVideoRequest,
    service: SearchService = Depends(get_search_service)
):
    """搜索视频"""
    try:
        logger.info(f"搜索视频: keyword={request.keyword}, offset={request.offset}, count={request.count}")
        result = await service.search_videos(
            request.keyword,
            request.offset,
            request.count,
            request.search_id,
            request.sort_type,
            request.publish_time,
            request.filter_duration,
            request.search_range,
        )
        return ApiResponse(data=result)
    except Exception as e:
        logger.error(f"搜索视频失败: {e}")
        import traceback
        traceback.print_exc()
        return ApiResponse(success=False, error=str(e))


@router.post("/user", response_model=ApiResponse[SearchPageResult])
async def search_users(
    request: SearchUserRequest,
    service: SearchService = Depends(get_search_service)
):
    """搜索用户"""
    try:
        logger.info(f"搜索用户: keyword={request.keyword}, offset={request.offset}, count={request.count}")
        result = await service.search_users(request.keyword, request.offset, request.count, request.search_id)
        return ApiResponse(data=result)
    except Exception as e:
        logger.error(f"搜索用户失败: {e}")
        return ApiResponse(success=False, error=str(e))


@router.post("/live", response_model=ApiResponse[SearchPageResult])
async def search_live(
    request: SearchLiveRequest,
    service: SearchService = Depends(get_search_service)
):
    """搜索直播"""
    try:
        logger.info(f"搜索直播: keyword={request.keyword}, offset={request.offset}, count={request.count}")
        result = await service.search_live(request.keyword, request.offset, request.count)
        return ApiResponse(data=result)
    except Exception as e:
        logger.error(f"搜索直播失败: {e}")
        return ApiResponse(success=False, error=str(e))
